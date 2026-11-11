"""
=====================================================================
 MODULE 2 of 4  -  bank_truck.py
=====================================================================
ROLE
    The mobile bank truck. A BankTruck IS-A BankAccount: its cash float
    behaves like an account (deposit, withdraw, balance, history, the
    opening-balance rule) and it adds truck-only features:
        * daily activity stored under each date
        * an automatic ID (TRK-001, TRK-002 ...)
        * an allocation counter that rises each time the dispatcher
          allocates the truck to a route
        * maintenance records
        * serving customers (deposit / withdrawal at the truck)

MAPPING TO THE BASE CLASS
    truck ID      -> account_number
    driver/teller -> owner
    cash float    -> balance / opening_balance

NEEDS   bank_account_system.py (same folder)
USED BY dispatcher.py and bank_main.py
=====================================================================
"""

# STEP 1: imports
import os
import sys
from abc import ABC, abstractmethod      # tools for ABSTRACTION
from datetime import date, datetime      # dates for daily activity and maintenance

# Make sure Python looks in THIS file's folder for our other modules.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bank_account_system import BankAccount      # the class we INHERIT from


# =====================================================================
# STEP 2: ABSTRACTION
# Reportable is an ABSTRACT class. It states WHAT every reportable object
# must do (describe itself with summary()) but not HOW. Any class that
# inherits it (BankTruck, Route, Dispatcher) MUST write its own summary(),
# otherwise Python refuses to create the object.
# =====================================================================
class Reportable(ABC):
    @abstractmethod                       # ABSTRACTION: no body here, subclasses supply it
    def summary(self):
        """Return a one-line description of the object."""


# =====================================================================
# STEP 3: INHERITANCE
# BankTruck gets EVERYTHING from BankAccount (account_number, owner,
# balance, opening_balance, transactions, deposit, withdraw, get_balance,
# get_details, show_history, check_withdrawal, to_dict ...) and from
# Reportable (the summary() rule).
# =====================================================================
class BankTruck(BankAccount, Reportable):

    # ----- STEP 3.1: constants (fixed values) -----
    STATUS_AVAILABLE = "Available"
    STATUS_ALLOCATED = "Allocated"
    STATUS_MAINTENANCE = "Under maintenance"
    VALID_STATUSES = (STATUS_AVAILABLE, STATUS_ALLOCATED, STATUS_MAINTENANCE)
    SERVICE_INTERVAL_DAYS = 90            # a truck needs a maintenance check every 90 days

    # CLASS ATTRIBUTE: one counter shared by all trucks (for automatic IDs)
    _next_truck_number = 1

    # -----------------------------------------------------------------
    # STEP 3.2: create a truck
    # -----------------------------------------------------------------
    def _init_(self, driver, plate, opening_cash, truck_id=None):
        # 1) validate the plate FIRST so a bad plate never uses up an ID
        plate = BankTruck.clean_plate(plate)                 # STATIC METHOD
        # 2) get the truck ID: automatic for a new truck, given when loading from file
        if truck_id is None:
            truck_id = BankTruck.generate_truck_id()         # CLASS METHOD (auto-increment)
        else:
            BankTruck._sync_counter(truck_id)                # keep the counter ahead
        # 3) INHERITANCE: super() runs BankAccount._init_, giving the truck
        #    all the normal account attributes.
        super()._init_(truck_id, driver, opening_cash)
        self.plate = plate

        # ENCAPSULATION: names starting with __ are PRIVATE. Code outside this
        # class cannot change them directly; it must use the methods below.
        self.__status = BankTruck.STATUS_AVAILABLE
        self.__route_name = None
        self.__allocation_count = 0        # +1 every time the dispatcher allocates the truck
        self.__last_service = None         # None = never checked, so it cannot be allocated yet
        self.__maintenance_log = []        # list of maintenance checks
        self.__daily_activity = {}         # {"2026-11-10": [entry, entry, ...]}

    # -----------------------------------------------------------------
    # STEP 3.3: CLASS METHODS  (receive the class itself as cls)
    # -----------------------------------------------------------------
    @classmethod
    def generate_truck_id(cls):
        """CLASS METHOD: produces TRK-001, TRK-002 ... automatically."""
        truck_id = f"TRK-{cls._next_truck_number:03d}"
        cls._next_truck_number += 1
        return truck_id

    @classmethod
    def _sync_counter(cls, truck_id):
        """CLASS METHOD: after loading TRK-007 from file, the next new ID is TRK-008."""
        try:
            number = int(str(truck_id).split("-")[1])
        except (IndexError, ValueError):
            return
        if number >= cls._next_truck_number:
            cls._next_truck_number = number + 1

    # -----------------------------------------------------------------
    # STEP 3.4: STATIC METHODS  (plain helpers: no self, no cls)
    # -----------------------------------------------------------------
    @staticmethod
    def clean_plate(plate):
        """STATIC METHOD: tidy a number plate (kca 123a -> KCA 123A)."""
        plate = str(plate).strip().upper()
        if not plate:
            raise ValueError("Number plate is required.")
        return plate

    @staticmethod
    def is_valid_status(status):
        """STATIC METHOD: is this one of the allowed statuses?"""
        return status in BankTruck.VALID_STATUSES

    @staticmethod
    def normalise_date(on_date=None):
        """STATIC METHOD: return YYYY-MM-DD (today if nothing given; error if badly written)."""
        if on_date is None or str(on_date).strip() == "":
            return date.today().isoformat()
        return datetime.strptime(str(on_date).strip(), "%Y-%m-%d").date().isoformat()

    @staticmethod
    def service_overdue(last_service, interval=SERVICE_INTERVAL_DAYS):
        """STATIC METHOD: True if never serviced, or the last check is too old."""
        if last_service is None:
            return True
        last = datetime.strptime(last_service, "%Y-%m-%d").date()
        return (date.today() - last).days > interval

    # -----------------------------------------------------------------
    # STEP 3.5: ENCAPSULATION - read-only properties.
    # There is no "setter", so outside code can READ these values but
    # cannot overwrite them (truck.status = "x" raises an error).
    # -----------------------------------------------------------------
    @property
    def status(self):
        return self.__status

    @property
    def route_name(self):
        return self.__route_name

    @property
    def allocation_count(self):
        return self.__allocation_count

    @property
    def last_service(self):
        return self.__last_service

    def needs_service(self):
        """True when a maintenance check is due."""
        return BankTruck.service_overdue(self.__last_service)

    # -----------------------------------------------------------------
    # STEP 3.6: DAILY ACTIVITY (every event stored under its date)
    # -----------------------------------------------------------------
    def log_activity(self, kind, amount=0.0, note="", on_date=None):
        """Store one entry (time, type, amount, balance after, note) under a date."""
        day = BankTruck.normalise_date(on_date)
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "type": kind,                  # Deposit / Withdrawal / Allocation / Maintenance ...
            "amount": amount,
            "balance": self.balance,
            "note": note,
        }
        self.__daily_activity.setdefault(day, []).append(entry)

    def get_activity(self, on_date=None):
        """Return a COPY of the day's entries (the private data stays protected)."""
        day = BankTruck.normalise_date(on_date)
        return list(self.__daily_activity.get(day, []))

    def activity_dates(self):
        return sorted(self.__daily_activity)

    def daily_totals(self, on_date=None):
        """(money collected, money paid out) for the day."""
        entries = self.get_activity(on_date)
        deposits = sum(e["amount"] for e in entries if e["type"] == "Deposit")
        withdrawals = sum(e["amount"] for e in entries if e["type"] == "Withdrawal")
        return round(deposits, 2), round(withdrawals, 2)

    def transaction_count(self, on_date=None):
        """How many money transactions happened on the day."""
        return sum(1 for e in self.get_activity(on_date) if e["type"] in ("Deposit", "Withdrawal"))

    def show_daily_activity(self, on_date=None):
        """Print everything the truck did on one date."""
        day = BankTruck.normalise_date(on_date)
        entries = self.get_activity(day)
        print(f"\n--- {self.account_number} | {day} | Route: {self.__route_name or 'none'} ---")
        if not entries:
            print("No activity recorded for this date.")
            return
        for e in entries:
            if e["type"] == "Deposit":
                amount_text = "+" + self.format_money(e["amount"])
            elif e["type"] == "Withdrawal":
                amount_text = "-" + self.format_money(e["amount"])
            else:
                amount_text = ""
            print(f"{e['time']}  {e['type']:<12}{amount_text:>14}  "
                  f"Cash: {self.format_money(e['balance'])}  {e['note']}")
        deposits, withdrawals = self.daily_totals(day)
        print(f"Totals -> collected: {self.format_money(deposits)} | "
              f"paid out: {self.format_money(withdrawals)} | "
              f"net: {self.format_money(deposits - withdrawals)}")

    # -----------------------------------------------------------------
    # STEP 3.7: DISPATCHER HOOKS (the dispatcher calls these)
    # -----------------------------------------------------------------
    def record_allocation(self, route_name):
        """The dispatcher allocates this truck: the counter goes up automatically."""
        self.__allocation_count += 1                          # AUTO-INCREMENT per allocation
        self.__route_name = route_name
        self.__status = BankTruck.STATUS_ALLOCATED
        self.log_activity("Allocation",
                          note=f"Allocated to {route_name} (allocation #{self.__allocation_count})")

    def release_route(self):
        """The dispatcher takes the truck off its route."""
        released = self.__route_name
        self.__route_name = None
        if self.__status == BankTruck.STATUS_ALLOCATED:
            self.__status = BankTruck.STATUS_AVAILABLE
        if released:
            self.log_activity("Released", note=f"Removed from {released}")
        return released

    def record_maintenance(self, passed, notes="", on_date=None):
        """
        Add a maintenance check.
          PASSED -> the service date is updated; a truck under maintenance becomes available.
          FAILED -> the truck is pulled off its route and blocked until it passes.
        Returns the route that was freed (or None) so the dispatcher can release it.
        """
        day = BankTruck.normalise_date(on_date)
        result = "PASSED" if passed else "FAILED"
        self.__maintenance_log.append({"date": day, "result": result, "notes": notes})
        freed_route = None
        if passed:
            self.__last_service = day
            if self.__status == BankTruck.STATUS_MAINTENANCE:
                self.__status = BankTruck.STATUS_AVAILABLE
        else:
            freed_route = self.__route_name
            self.__route_name = None
            self.__status = BankTruck.STATUS_MAINTENANCE
        self.log_activity("Maintenance", note=f"{result}. {notes}".strip(), on_date=day)
        return freed_route

    def show_maintenance_history(self):
        print(f"\n--- Maintenance history: {self.account_number} ---")
        if not self.__maintenance_log:
            print("No maintenance checks yet.")
        for record in self.__maintenance_log:
            print(f"{record['date']}  {record['result']:<7} {record['notes']}")

    # -----------------------------------------------------------------
    # STEP 3.8: POLYMORPHISM
    # The methods below have the SAME NAME as BankAccount methods but
    # behave differently for a truck. Code that calls account.deposit(...)
    # works on a BankAccount and on a BankTruck alike.
    # -----------------------------------------------------------------
    def deposit(self, amount, note=""):              # POLYMORPHISM (override)
        if self.__status == BankTruck.STATUS_MAINTENANCE:
            print("Truck is under maintenance. Transactions are blocked.")
            return
        before = self.balance
        super().deposit(amount)                      # INHERITANCE: reuse the parent's logic
        if self.balance != before:                   # only log if money really moved
            self.log_activity("Deposit", round(self.balance - before, 2), note)

    def withdraw(self, amount, note=""):             # POLYMORPHISM (override)
        if self.__status == BankTruck.STATUS_MAINTENANCE:
            print("Truck is under maintenance. Transactions are blocked.")
            return
        before = self.balance
        super().withdraw(amount)                     # keeps the opening-balance rule
        if self.balance != before:
            self.log_activity("Withdrawal", round(before - self.balance, 2), note)

    def get_details(self):                           # POLYMORPHISM (override + extend)
        super().get_details()                        # print the normal account details first
        print("Plate:           ", self.plate)
        print("Status:          ", self.__status)
        print("Route:           ", self.__route_name or "none")
        print("Allocations:     ", self.__allocation_count)
        print("Last service:    ", self.__last_service or "never")
        print("Service due:     ", "YES" if self.needs_service() else "no")

    def summary(self):                               # ABSTRACTION implemented here
        return (f"{self.account_number} | {self.plate} | Driver: {self.owner} | "
                f"{self._status} | Route: {self._route_name or 'none'} | "
                f"Cash: {self.format_money(self.balance)} | "
                f"Allocations: {self.__allocation_count}")

    # -----------------------------------------------------------------
    # STEP 3.9: SERVING CUSTOMERS (this is what makes a truck functional)
    # -----------------------------------------------------------------
    def can_serve(self):
        """A truck can only serve customers while it is on a route."""
        if self.__status == BankTruck.STATUS_MAINTENANCE:
            return False, "This truck is under maintenance."
        if self.__status != BankTruck.STATUS_ALLOCATED:
            return False, "This truck has no route yet. Ask the dispatcher to allocate it."
        return True, ""

    def serve_deposit(self, customer, amount):
        """Customer gives cash to the teller: the customer's balance AND the truck's cash go up."""
        ok, message = self.can_serve()
        if not ok:
            print(message)
            return False
        if not BankAccount.is_valid_amount(amount):
            print("Invalid amount.")
            return False
        note = f"Customer {customer.account_number} ({customer.owner})"
        print("Customer account:")
        customer.deposit(amount)                     # INHERITANCE: the same BankAccount method
        print("Truck cash:")
        self.deposit(amount, note)
        return True

    def serve_withdrawal(self, customer, amount):
        """
        Teller pays cash out. BOTH rules must pass first:
          1) the customer's balance may not drop below their opening balance
          2) the truck's cash may not drop below its opening float
        If either fails, nothing at all is changed.
        """
        ok, message = self.can_serve()
        if not ok:
            print(message)
            return False
        if not BankAccount.is_valid_amount(amount):
            print("Invalid amount.")
            return False
        allowed, message = customer.check_withdrawal(amount)
        if not allowed:
            print("Customer: " + message)
            return False
        allowed, message = self.check_withdrawal(amount)
        if not allowed:
            print("The truck does not have enough cash to pay this out. " + message)
            return False
        note = f"Customer {customer.account_number} ({customer.owner})"
        print("Customer account:")
        customer.withdraw(amount)
        print("Truck cash:")
        self.withdraw(amount, note)
        return True

    # -----------------------------------------------------------------
    # STEP 3.10: SAVING AND LOADING (extends the parent's versions)
    # -----------------------------------------------------------------
    def to_dict(self):                               # POLYMORPHISM (override + extend)
        data = super().to_dict()                     # the normal account data...
        data.update({                                # ...plus the truck-only data
            "plate": self.plate,
            "status": self.__status,
            "route_name": self.__route_name,
            "allocation_count": self.__allocation_count,
            "last_service": self.__last_service,
            "maintenance_log": self.__maintenance_log,
            "daily_activity": self.__daily_activity,
        })
        return data

    @classmethod
    def from_dict(cls, data):                        # CLASS METHOD (override)
        truck = cls(data["owner"], data["plate"], data["opening_balance"],
                    truck_id=data["account_number"])
        truck.balance = data["balance"]
        truck.transactions = data.get("transactions", [])
        truck.__status = data.get("status", cls.STATUS_AVAILABLE)
        truck.__route_name = data.get("route_name")
        truck.__allocation_count = data.get("allocation_count", 0)
        truck.__last_service = data.get("last_service")
        truck.__maintenance_log = data.get("maintenance_log", [])
        truck.__daily_activity = data.get("daily_activity", {})
        return truck