"""
dispatcher.py  -  Dispatcher module for the mobile bank trucks

The dispatcher:
  * registers trucks and routes
  * allocates trucks to routes (each allocation gets an automatic number)
  * lists available trucks, all routes and routes NOT yet allocated
  * runs maintenance checks (a failed check pulls the truck off its route)

Run this file directly to use the dispatcher menu:   python dispatcher.py
"""

import json
import os
import sys

# Always look for our other files in this file's own folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bank_account_system import BankAccount
from bank_truck import BankTruck, Reportable

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dispatch_data.json")


# =====================================================================
# Route  -  inherits the abstract Reportable class (ABSTRACTION)
# =====================================================================
class Route(Reportable):
    def __init__(self, name, stops, days):
        self.name = name.strip()
        self.stops = list(stops)
        self.days = list(days)
        # ENCAPSULATION: private. Only assign() / clear() can change it,
        # so a route can never be given to two trucks by accident.
        self.__truck_id = None

    @property                                   # ENCAPSULATION: read-only access
    def truck_id(self):
        return self.__truck_id

    @property
    def is_allocated(self):
        return self.__truck_id is not None

    def assign(self, truck_id):
        self.__truck_id = truck_id

    def clear(self):
        self.__truck_id = None

    @staticmethod                               # STATIC METHOD: no self / cls needed
    def parse_list(text):
        """'kutus, wanguru ,mwea' -> ['Kutus', 'Wanguru', 'Mwea']"""
        return [part.strip().title() for part in str(text).split(",") if part.strip()]

    @classmethod                                # CLASS METHOD: builds a Route from text
    def from_text(cls, name, stops_text, days_text):
        return cls(name, cls.parse_list(stops_text), cls.parse_list(days_text))

    def summary(self):                          # ABSTRACTION implemented (POLYMORPHISM:
        owner = self.__truck_id or "NOT ALLOCATED"   # same name as Truck.summary, different text)
        return (f"{self.name} | Stops: {', '.join(self.stops)} | "
                f"Days: {', '.join(self.days)} | Truck: {owner}")

    def to_dict(self):
        return {"name": self.name, "stops": self.stops, "days": self.days,
                "truck_id": self.__truck_id}

    @classmethod
    def from_dict(cls, data):
        route = cls(data["name"], data["stops"], data["days"])
        route.__truck_id = data.get("truck_id")
        return route


# =====================================================================
# Dispatcher  -  also a Reportable (ABSTRACTION + INHERITANCE)
# =====================================================================
class Dispatcher(Reportable):
    # CLASS ATTRIBUTE: automatic increment for every allocation made
    _allocation_counter = 0

    def __init__(self, name="Main Dispatcher"):
        self.name = name
        # ENCAPSULATION: the collections are private. The rest of the program
        # must go through the dispatcher's methods (and the rules inside them).
        self.__trucks = {}
        self.__routes = {}
        self.__allocations = []

    # ---------------- class method: auto-incrementing allocation number
    @classmethod
    def next_allocation_no(cls):
        """CLASS METHOD: ALLOC-001, ALLOC-002 ... generated automatically."""
        cls._allocation_counter += 1
        return f"ALLOC-{cls._allocation_counter:03d}"

    # ---------------- read access (returns copies / lists, not the private dicts)
    @property
    def trucks(self):
        return list(self.__trucks.values())

    @property
    def routes(self):
        return list(self.__routes.values())

    @property
    def allocations(self):
        return list(self.__allocations)

    def get_truck(self, truck_id):
        return self.__trucks.get(str(truck_id).strip().upper())

    def get_route(self, name):
        return self.__routes.get(str(name).strip().lower())

    # ---------------- registering
    def register_truck(self, driver, plate, opening_cash):
        if not str(driver).strip():
            return False, "Driver name is required.", None
        if not BankAccount.is_valid_amount(opening_cash):      # inherited static method
            return False, "Opening cash must be a number above 0.", None
        try:
            truck = BankTruck(str(driver).strip(), plate, opening_cash)
        except ValueError as error:
            return False, str(error), None
        self.__trucks[truck.account_number] = truck
        self.save()
        return True, f"Truck registered with ID {truck.account_number}.", truck

    def add_route(self, name, stops_text, days_text):
        route = Route.from_text(name, stops_text, days_text)
        if not route.name:
            return False, "Route name is required."
        if not route.stops:
            return False, "Enter at least one stop."
        if route.name.lower() in self.__routes:
            return False, "A route with that name already exists."
        self.__routes[route.name.lower()] = route
        self.save()
        return True, f"Route '{route.name}' added."

    # ---------------- lists
    def available_trucks(self):
        """Trucks that can be allocated right now."""
        return [t for t in self.trucks
                if t.status == BankTruck.STATUS_AVAILABLE and not t.needs_service()]

    def unallocated_routes(self):
        """Routes with no truck yet."""
        return [r for r in self.routes if not r.is_allocated]

    def trucks_needing_maintenance(self):
        return [t for t in self.trucks
                if t.status == BankTruck.STATUS_MAINTENANCE or t.needs_service()]

    # ---------------- allocation
    def allocate(self, truck_id, route_name):
        truck = self.get_truck(truck_id)
        route = self.get_route(route_name)
        if truck is None:
            return False, "Truck not found."
        if route is None:
            return False, "Route not found."
        if route.is_allocated:
            return False, f"Route '{route.name}' already has truck {route.truck_id}."
        if truck.status == BankTruck.STATUS_ALLOCATED:
            return False, f"{truck.account_number} is already on route '{truck.route_name}'."
        if truck.status == BankTruck.STATUS_MAINTENANCE:
            return False, f"{truck.account_number} is under maintenance."
        if truck.needs_service():
            return False, (f"{truck.account_number} needs a maintenance check "
                           f"before it can be allocated.")

        allocation_no = Dispatcher.next_allocation_no()        # AUTO-INCREMENT
        truck.record_allocation(route.name)                    # truck counts it too
        route.assign(truck.account_number)
        self.__allocations.append({
            "allocation_no": allocation_no,
            "truck_id": truck.account_number,
            "route": route.name,
            "date": BankTruck.normalise_date(),
        })
        self.save()
        return True, (f"{allocation_no}: {truck.account_number} allocated to '{route.name}' "
                      f"(allocation #{truck.allocation_count} for this truck).")

    def deallocate(self, truck_id):
        truck = self.get_truck(truck_id)
        if truck is None:
            return False, "Truck not found."
        if truck.route_name is None:
            return False, "That truck is not on a route."
        route = self.get_route(truck.route_name)
        truck.release_route()
        if route:
            route.clear()
        self.save()
        return True, f"{truck.account_number} removed from its route."

    # ---------------- maintenance
    def run_maintenance_check(self, truck_id, passed, notes="", on_date=None):
        truck = self.get_truck(truck_id)
        if truck is None:
            return False, "Truck not found."
        try:
            freed = truck.record_maintenance(passed, notes, on_date)
        except ValueError:
            return False, "Use the date format YYYY-MM-DD."
        if freed:                                   # failed check: route goes back to the pool
            route = self.get_route(freed)
            if route:
                route.clear()
        self.save()
        if passed:
            return True, f"{truck.account_number} passed. It can be allocated."
        extra = f" Route '{freed}' is now unallocated." if freed else ""
        return True, f"{truck.account_number} FAILED and is under maintenance.{extra}"

    # ---------------- report (ABSTRACTION implemented)
    def summary(self):
        return (f"{self.name}: {len(self.__trucks)} trucks "
                f"({len(self.available_trucks())} available), "
                f"{len(self.__routes)} routes "
                f"({len(self.unallocated_routes())} unallocated), "
                f"{len(self.__allocations)} allocations made")

    def show_report(self):
        print("\n=== DISPATCH REPORT ===")
        print(self.summary())
        print("\nTrucks:")
        for truck in self.trucks:
            print(" ", truck.summary())               # POLYMORPHISM: truck.summary()
        print("\nRoutes:")
        for route in self.routes:
            print(" ", route.summary())               # POLYMORPHISM: route.summary()
        print("\nAllocation history:")
        for a in self.__allocations:
            print(f"  {a['allocation_no']} | {a['date']} | {a['truck_id']} -> {a['route']}")
        if not self.__allocations:
            print("  none yet")

    # ---------------- saving / loading
    def save(self):
        data = {
            "name": self.name,
            "allocation_counter": Dispatcher._allocation_counter,
            "trucks": [t.to_dict() for t in self.__trucks.values()],
            "routes": [r.to_dict() for r in self.__routes.values()],
            "allocations": self.__allocations,
        }
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)

    @classmethod
    def load(cls, name="Main Dispatcher"):
        """CLASS METHOD: builds a Dispatcher from the saved file (or a new one)."""
        dispatcher = cls(name)  
        if not os.path.exists(DATA_FILE):
            return dispatcher
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            dispatcher.name = data.get("name", name)
            cls._allocation_counter = data.get("allocation_counter", 0)
            for item in data.get("trucks", []):
                truck = BankTruck.from_dict(item)
                dispatcher.__trucks[truck.account_number] = truck
            for item in data.get("routes", []):
                route = Route.from_dict(item)
                dispatcher.__routes[route.name.lower()] = route
            dispatcher._Dispatcher__allocations = data.get("allocations", [])
        except (json.JSONDecodeError, KeyError, ValueError):
            print("Warning: could not read dispatch data. Starting empty.")
        return dispatcher


# =====================================================================
# Console menu
# =====================================================================
def ask_amount(prompt):
    try:
        return float(input(prompt))
    except ValueError:
        return None


def show_list(title, items):
    print(f"\n--- {title} ---")
    if not items:
        print("None.")
    for item in items:
        print(" ", item.summary())


def allocate_flow(dispatcher, route_name=None):
    show_list("Available trucks", dispatcher.available_trucks())
    truck_id = input("Truck ID to allocate (e.g. TRK-001): ").strip()
    if route_name is None:
        show_list("Unallocated routes", dispatcher.unallocated_routes())
        route_name = input("Route name: ").strip()
    ok, message = dispatcher.allocate(truck_id, route_name)
    print(message)


def maintenance_flow(dispatcher):
    show_list("Trucks needing a check", dispatcher.trucks_needing_maintenance())
    truck_id = input("Truck ID to check: ").strip()
    result = input("Did it pass? (y/n): ").strip().lower()
    notes = input("Notes: ").strip()
    when = input("Date YYYY-MM-DD (Enter = today): ").strip()
    ok, message = dispatcher.run_maintenance_check(truck_id, result == "y", notes, when or None)
    print(message)


def truck_menu(dispatcher):
    truck = dispatcher.get_truck(input("Truck ID: ").strip())
    if truck is None:
        print("Truck not found.")
        return
    while True:
        print(f"\n--- {truck.account_number} ({truck.owner}) ---")
        print("1 Deposit | 2 Withdraw | 3 Today's activity | 4 Activity by date | "
              "5 Details | 6 History | 0 Back")
        choice = input("Choose: ").strip()
        if choice == "1":
            truck.deposit(ask_amount("Amount collected: "))
            dispatcher.save()
        elif choice == "2":
            truck.show_withdrawal_notice()
            truck.withdraw(ask_amount("Amount paid out: "))
            dispatcher.save()
        elif choice == "3":
            truck.show_daily_activity()
        elif choice == "4":
            day = input("Date YYYY-MM-DD: ").strip()
            try:
                truck.show_daily_activity(day)
            except ValueError:
                print("Use the date format YYYY-MM-DD.")
        elif choice == "5":
            truck.get_details()
        elif choice == "6":
            truck.show_history()
        elif choice == "0":
            break
        else:
            print("Invalid choice.")


def run_menu(dispatcher):
    while True:
        print(f"\n=== {dispatcher.name} ===")
        print("1 Register truck | 2 Add route | 3 All trucks | 4 All routes | 5 Unallocated routes")
        print("6 Allocate truck | 7 Deallocate | 8 Maintenance check | 9 Truck cash & activity")
        print("10 Report | 0 Exit")
        choice = input("Choose: ").strip().rstrip(".")

        if choice == "1":
            driver = input("Driver name: ").strip()
            plate = input("Number plate: ").strip()
            cash = ask_amount("Opening cash float: ")
            print(dispatcher.register_truck(driver, plate, cash)[1])
        elif choice == "2":
            name = input("Route name: ").strip()
            stops = input("Stops (comma separated): ").strip()
            days = input("Visit days (comma separated): ").strip()
            print(dispatcher.add_route(name, stops, days)[1])
        elif choice == "3":
            show_list("All trucks", dispatcher.trucks)
        elif choice == "4":
            show_list("All routes", dispatcher.routes)
        elif choice == "5":
            routes = dispatcher.unallocated_routes()
            show_list("Unallocated routes", routes)
            if routes and input("Allocate a truck now? (y/n): ").strip().lower() == "y":
                allocate_flow(dispatcher)
        elif choice == "6":
            allocate_flow(dispatcher)
        elif choice == "7":
            print(dispatcher.deallocate(input("Truck ID: ").strip())[1])
        elif choice == "8":
            maintenance_flow(dispatcher)
        elif choice == "9":
            truck_menu(dispatcher)
        elif choice == "10":
            dispatcher.show_report()
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")


def main():
    run_menu(Dispatcher.load())


if __name__ == "_main_":
    main()