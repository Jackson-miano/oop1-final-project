"""
=====================================================================
 MODULE 4 of 4  -  bank_main.py      <<< RUN THIS FILE >>>
=====================================================================
ROLE
    The single entry point that joins every module:

        1 Customer banking     -> bank_account_system.py  (register / log in)
        2 Dispatcher           -> dispatcher.py           (trucks, routes, maintenance)
        3 Bank truck terminal  -> bank_truck.py           (teller serves customers)

HOW THE DATA FLOWS
    accounts.json        <- customers (BankAccount objects)
    dispatch_data.json   <- trucks (BankTruck), routes and allocations
    A customer deposit at a truck updates BOTH files: the customer's
    balance and the truck's cash, and it is logged under today's date.

START WITH   python bank_main.py     (or Ctrl+F5 in VS Code)
=====================================================================
"""

# STEP 1: imports
import os
import sys

# Make sure Python looks in THIS file's folder for our other modules.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bank_account_system as bank                       # Module 1 (customers)
from bank_account_system import BankAccount
from bank_truck import BankTruck                         # Module 2 (trucks)
from dispatcher import Dispatcher, run_menu, show_list, ask_amount   # Module 3


# =====================================================================
# STEP 2: find a customer by account number
# =====================================================================
def find_customer():
    number = input("Customer account number: ").strip()
    customer = bank.accounts.get(number)
    if customer is None:
        print("Customer account not found. Register it under 'Customer banking' first.")
    return customer


# =====================================================================
# STEP 3: THE BANK TRUCK TERMINAL (the teller's screen)
# =====================================================================
def truck_terminal(dispatcher):
    # 3.1: load the latest customers, then show which trucks are working
    bank.load_accounts()
    on_route = [t for t in dispatcher.trucks if t.status == BankTruck.STATUS_ALLOCATED]
    show_list("Trucks currently on a route", on_route)

    # 3.2: choose a truck and make sure it is allowed to serve customers
    truck = dispatcher.get_truck(input("Truck ID: ").strip())
    if truck is None:
        print("Truck not found.")
        return
    ok, message = truck.can_serve()      # must be allocated and not under maintenance
    if not ok:
        print(message)
        return

    # 3.3: the teller's menu
    while True:
        print(f"\n--- {truck.account_number} | {truck.route_name} | teller: {truck.owner} ---")
        print("1 Customer deposit | 2 Customer withdrawal | 3 Customer balance")
        print("4 Today's activity | 5 Activity by date | 6 Truck details | 0 Back")
        choice = input("Choose: ").strip().rstrip(".")

        if choice == "1":
            customer = find_customer()
            if customer and truck.serve_deposit(customer, ask_amount("Amount received: ")):
                bank.save_accounts()     # save the customer's new balance
                dispatcher.save()        # save the truck's cash and daily activity
        elif choice == "2":
            customer = find_customer()
            if customer:
                customer.show_withdrawal_notice()
                if truck.serve_withdrawal(customer, ask_amount("Amount to pay out: ")):
                    bank.save_accounts()
                    dispatcher.save()
        elif choice == "3":
            customer = find_customer()
            if customer:
                print(f"{customer.owner}: balance "
                      f"{BankAccount.format_money(customer.get_balance())}")
        elif choice == "4":
            truck.show_daily_activity()
        elif choice == "5":
            try:
                truck.show_daily_activity(input("Date YYYY-MM-DD: ").strip())
            except ValueError:
                print("Use the date format YYYY-MM-DD.")
        elif choice == "6":
            truck.get_details()
        elif choice == "0":
            break
        else:
            print("Invalid choice.")


# =====================================================================
# STEP 4: THE MAIN MENU
# =====================================================================
def main():
    bank.load_accounts()                 # load customers once at the start
    dispatcher = Dispatcher.load()       # load trucks, routes and allocations
    while True:
        print(f"\n=== {BankAccount.bank_name} ===")
        print("1 Customer banking | 2 Dispatcher | 3 Bank truck terminal | 0 Exit")
        choice = input("Choose: ").strip().rstrip(".")

        if choice == "1":
            bank.customer_menu()         # Register / Log in / Back
        elif choice == "2":
            run_menu(dispatcher)         # dispatcher menu, 0 returns here
        elif choice == "3":
            truck_terminal(dispatcher)
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")


# STEP 5: start the program only when this file is run directly.
if __name__ == "__main__":
    main()
