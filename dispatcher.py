"""
=====================================================================
 MODULE 3 of 4  -  dispatcher.py
=====================================================================
ROLE
    The dispatcher's office. It:
        * registers trucks and routes
        * allocates trucks to routes (every allocation gets an
          automatic number: ALLOC-001, ALLOC-002 ...)
        * lists available trucks, all routes and routes NOT yet allocated
        * runs maintenance checks (a failed check pulls the truck off
          its route and puts the route back on the unallocated list)
        * prints reports and a daily summary of all trucks

NEEDS   bank_account_system.py and bank_truck.py (same folder)
USED BY bank_main.py   (this file can also be run on its own)
DATA    dispatch_data.json - trucks, routes and allocations, saved automatically
=====================================================================
"""

# STEP 1: imports
import json
import os
import sys

# Make sure Python looks in THIS file's folder for our other modules.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bank_account_system import BankAccount
from bank_truck import BankTruck, Reportable

# Where dispatcher data is saved (next to this file).
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dispatch_data.json")


# =====================================================================
# STEP 2: THE Route CLASS
# A route inherits the abstract class Reportable (ABSTRACTION), so it
# must write its own summary().
# =====================================================================
class Route(Reportable):
    def __init__(self, name, stops, days):
        self.name = name.strip()
        self.stops = list(stops)            # villages / markets, in order
        self.days = list(days)              # scheduled visit days
        # ENCAPSULATION: private. Only assign() and clear() can change it,
        # so a route can never be given to two trucks by accident.
        self.__truck_id = None

    # ----- read-only access (ENCAPSULATION) -----
    @property
    def truck_id(self):
        return self.__truck_id

    @property
    def is_allocated(self):
        return self.__truck_id is not None

    # ----- the only ways to change the private value -----
    def assign(self, truck_id):
        self.__truck_id = truck_id

    def clear(self):
        self.__truck_id = None

    # ----- STATIC METHOD: no self / cls needed -----
    @staticmethod
    def parse_list(text):
        """STATIC METHOD: 'kutus, wanguru ,mwea' -> ['Kutus', 'Wanguru', 'Mwea']"""
        return [part.strip().title() for part in str(text).split(",") if part.strip()]

    # ----- CLASS METHOD: builds a Route from typed text -----
    @classmethod
    def from_text(cls, name, stops_text, days_text):
        """CLASS METHOD: create a Route from comma-separated text."""
        return cls(name, cls.parse_list(stops_text), cls.parse_list(days_text))

    # ----- ABSTRACTION implemented. POLYMORPHISM: same name as
    #       BankTruck.summary() but it describes a route. -----
    def summary(self):
        holder = self.__truck_id or "NOT ALLOCATED"
        return (f"{self.name} | Stops: {', '.join(self.stops)} | "
                f"Days: {', '.join(self.days)} | Truck: {holder}")

    # ----- saving / loading one route -----
    def to_dict(self):
        return {"name": self.name, "stops": self.stops, "days": self.days,
                "truck_id": self.__truck_id}

    @classmethod
    def from_dict(cls, data):
        route = cls(data["name"], data["stops"], data["days"])
        route.__truck_id = data.get("truck_id")
        return route


# =====================================================================
# STEP 3: THE Dispatcher CLASS
# Also a Reportable (ABSTRACTION + INHERITANCE).
# =====================================================================
class Dispatcher(Reportable):

    # CLASS ATTRIBUTE: one counter, automatically increased for every allocation
    _allocation_counter = 0

    # -----------------------------------------------------------------
    # STEP 3.1: create a dispatcher
    # -----------------------------------------------------------------
    def __init__(self, name="Main Dispatcher"):
        self.name = name
        # ENCAPSULATION: these collections are private. The rest of the
        # program must go through the dispatcher's methods, which contain
        # the rules (no double allocation, maintenance check first ...).
        self.__trucks = {}                  # {"TRK-001": BankTruck}
        self.__routes = {}                  # {"mwea route": Route}
        self.__allocations = []             # history of every allocation

    @classmethod
    def next_allocation_no(cls):
        """CLASS METHOD: ALLOC-001, ALLOC-002 ... generated automatically."""
        cls._allocation_counter += 1
        return f"ALLOC-{cls._allocation_counter:03d}"

    # -----------------------------------------------------------------
    # STEP 3.2: read access (returns copies, never the private dictionaries)
    # -----------------------------------------------------------------
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

    # -----------------------------------------------------------------
    # STEP 3.3: registering trucks and routes
    # Each method returns (success, message) so the menu can show the result.
    # -----------------------------------------------------------------
    def register_truck(self, driver, plate, opening_cash):
        if not str(driver).strip():
            return False, "Driver name is required.", None
        if not BankAccount.is_valid_amount(opening_cash):      # inherited static method
            return False, "Opening cash must be a number above 0.", None
        try:
            truck = BankTruck(str(driver).strip(), plate, round(opening_cash, 2))
        except ValueError as error:                            # e.g. empty plate
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

    # -----------------------------------------------------------------
    # STEP 3.4: lists the dispatcher needs
    # -----------------------------------------------------------------
    def available_trucks(self):
        """Trucks that can be allocated right now (free AND maintenance up to date)."""
        return [t for t in self.trucks
                if t.status == BankTruck.STATUS_AVAILABLE and not t.needs_service()]

    def unallocated_routes(self):
        """Routes that have no truck yet."""
        return [r for r in self.routes if not r.is_allocated]

    def trucks_needing_maintenance(self):
        """Trucks that failed a check, or whose check is due / never done."""
        return [t for t in self.trucks
                if t.status == BankTruck.STATUS_MAINTENANCE or t.needs_service()]

    # -----------------------------------------------------------------
    # STEP 3.5: ALLOCATION (truck -> route)
    # Every rule is checked BEFORE anything is changed.
    # -----------------------------------------------------------------
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

        # all checks passed: make the allocation
        allocation_no = Dispatcher.next_allocation_no()        # AUTO-INCREMENT (class method)
        truck.record_allocation(route.name)                    # the truck counts it too
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
        """Take a truck off its route so the route goes back to the unallocated list."""
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

    # -----------------------------------------------------------------
    # STEP 3.6: MAINTENANCE CHECKS
    # -----------------------------------------------------------------
    def run_maintenance_check(self, truck_id, passed, notes="", on_date=None):
        truck = self.get_truck(truck_id)
        if truck is None:
            return False, "Truck not found."
        try:
            freed = truck.record_maintenance(passed, notes, on_date)
        except ValueError:                           # badly written date
            return False, "Use the date format YYYY-MM-DD."
        if freed:                                    # failed check: the route returns to the pool
            route = self.get_route(freed)
            if route:
                route.clear()
        self.save()
        if passed:
            return True, f"{truck.account_number} passed. It can be allocated."
        extra = f" Route '{freed}' is now unallocated." if freed else ""
        return True, f"{truck.account_number} FAILED and is under maintenance.{extra}"

    # -----------------------------------------------------------------
    # STEP 3.7: REPORTS
    # -----------------------------------------------------------------
    def summary(self):                               # ABSTRACTION implemented
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

    def show_daily_summary(self, on_date=None):
        """Money collected and paid out by EVERY truck on one date."""
        day = BankTruck.normalise_date(on_date)      # raises ValueError for a bad date
        print(f"\n=== DAILY SUMMARY {day} ===")
        total_in = total_out = 0.0
        for truck in self.trucks:
            collected, paid = truck.daily_totals(day)
            total_in += collected
            total_out += paid
            print(f"{truck.account_number} | Route: {truck.route_name or 'none'} | "
                  f"transactions: {truck.transaction_count(day)} | "
                  f"collected {BankAccount.format_money(collected)} | "
                  f"paid out {BankAccount.format_money(paid)}")
        if not self.trucks:
            print("No trucks registered.")
        print(f"ALL TRUCKS -> collected {BankAccount.format_money(total_in)} | "
              f"paid out {BankAccount.format_money(total_out)} | "
              f"net {BankAccount.format_money(total_in - total_out)}")

    # -----------------------------------------------------------------
    # STEP 3.8: SAVING AND LOADING (dispatch_data.json)
    # -----------------------------------------------------------------
    def save(self):
        data = {
            "name": self.name,
            "allocation_counter": Dispatcher._allocation_counter,
            "trucks": [t.to_dict() for t in self.__trucks.values()],
            "routes": [r.to_dict() for r in self.__routes.values()],
            "allocations": self.__allocations,
        }
        with open(DATA_FILE, "w") as file:
            json.dump(data, file, indent=4)

    @classmethod
    def load(cls, name="Main Dispatcher"):
        """CLASS METHOD: build a Dispatcher from the saved file (or a new empty one)."""
        dispatcher = cls(name)
        if not os.path.exists(DATA_FILE):
            return dispatcher                        # first run: nothing saved yet
        try:
            with open(DATA_FILE, "r") as file:
                data = json.load(file)
            dispatcher.name = data.get("name", name)
            cls._allocation_counter = data.get("allocation_counter", 0)
            for item in data.get("trucks", []):
                truck = BankTruck.from_dict(item)
                dispatcher.__trucks[truck.account_number] = truck
            for item in data.get("routes", []):
                route = Route.from_dict(item)
                dispatcher.__routes[route.name.lower()] = route
            dispatcher.__allocations = data.get("allocations", [])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            print("Warning: could not read dispatch data. Starting empty.")
        return dispatcher


# =====================================================================
# STEP 4: MENU HELPERS (screens that call the methods above)
# =====================================================================
def ask_amount(prompt):
    """Ask for a number; return None if the user typed text."""
    try:
        return float(input(prompt))
    except ValueError:
        return None


def show_list(title, items):
    """Print a titled list of Reportable objects using each one's summary()."""
    print(f"\n--- {title} ---")
    if not items:
        print("None.")
    for item in items:
        print(" ", item.summary())


def allocate_flow(dispatcher):
    """Show what is free, then ask which truck goes on which route."""
    show_list("Available trucks", dispatcher.available_trucks())
    show_list("Unallocated routes", dispatcher.unallocated_routes())
    truck_id = input("Truck ID to allocate (e.g. TRK-001): ").strip()
    route_name = input("Route name: ").strip()
    print(dispatcher.allocate(truck_id, route_name)[1])


def maintenance_flow(dispatcher):
    """Record a maintenance check for one truck."""
    show_list("Trucks needing a check", dispatcher.trucks_needing_maintenance())
    truck_id = input("Truck ID to check: ").strip()
    result = input("Did it pass? (y/n): ").strip().lower()
    notes = input("Notes: ").strip()
    when = input("Date YYYY-MM-DD (Enter = today): ").strip()
    print(dispatcher.run_maintenance_check(truck_id, result == "y", notes, when or None)[1])


def truck_menu(dispatcher):
    """Dispatcher's view of one truck: cash, daily activity and maintenance history."""
    truck = dispatcher.get_truck(input("Truck ID: ").strip())
    if truck is None:
        print("Truck not found.")
        return
    while True:
        print(f"\n--- {truck.account_number} ({truck.owner}) ---")
        print("1 Cash in | 2 Cash out | 3 Today's activity | 4 Activity by date")
        print("5 Details | 6 History | 7 Maintenance history | 0 Back")
        choice = input("Choose: ").strip().rstrip(".")

        if choice == "1":
            if truck.deposit(ask_amount("Amount collected: ")):
                dispatcher.save()
        elif choice == "2":
            truck.show_withdrawal_notice()
            if truck.withdraw(ask_amount("Amount paid out: ")):
                dispatcher.save()
        elif choice == "3":
            truck.show_daily_activity()
        elif choice == "4":
            try:
                truck.show_daily_activity(input("Date YYYY-MM-DD: ").strip())
            except ValueError:
                print("Use the date format YYYY-MM-DD.")
        elif choice == "5":
            truck.get_details()
        elif choice == "6":
            truck.show_history()
        elif choice == "7":
            truck.show_maintenance_history()
        elif choice == "0":
            break
        else:
            print("Invalid choice.")


# =====================================================================
# STEP 5: THE DISPATCHER MENU
# =====================================================================
def run_menu(dispatcher):
    while True:
        print(f"\n=== {dispatcher.name} ===")
        print("1 Register truck | 2 Add route | 3 All trucks | 4 All routes | 5 Unallocated routes")
        print("6 Allocate truck | 7 Deallocate | 8 Maintenance check | 9 Truck cash & activity")
        print("10 Report | 11 Daily summary | 0 Back")
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
        elif choice == "11":
            when = input("Date YYYY-MM-DD (Enter = today): ").strip()
            try:
                dispatcher.show_daily_summary(when or None)
            except ValueError:
                print("Use the date format YYYY-MM-DD.")
        elif choice == "0":
            break
        else:
            print("Invalid choice.")


def main():
    """Run the dispatcher on its own."""
    run_menu(Dispatcher.load())


# Start only when this file is run directly (NOT when bank_main.py imports it).
if __name__ == "__main__":
    main()
