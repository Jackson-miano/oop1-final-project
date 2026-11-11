"""
bank_main.py  -  ONE program that joins everything

    1 Customer banking      (register / log in / deposit / withdraw)
    2 Dispatcher            (trucks, routes, allocation, maintenance)
    3 Bank truck terminal   (a teller serves customers at an allocated truck)

Run THIS file:   python bank_main.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bank_account_system as bank
from bank_account_system import BankAccount
from bank_truck import BankTruck
from dispatcher import Dispatcher, run_menu, show_list, ask_amount


def find_customer():
    number = input("Customer account number: ").strip()
    customer = bank.accounts.get(number)
    if customer is None:
        print("Customer account not found. Register it under 'Customer banking' first.")
    return customer


def truck_terminal(dispatcher):
    """The teller's screen on a bank truck."""
    bank.load_accounts()                       # make sure customers are loaded
    on_route = [t for t in dispatcher.trucks if t.status == BankTruck.STATUS_ALLOCATED]
    show_list("Trucks currently on a route", on_route)

    truck = dispatcher.get_truck(input("Truck ID: ").strip())
    if truck is None:
        print("Truck not found.")
        return
    ok, message = truck.can_serve()
    if not ok:
        print(message)
        return

    while True:
        print(f"\n--- {truck.account_number} | {truck.route_name} | teller: {truck.owner} ---")
        print("1 Customer deposit | 2 Customer withdrawal | 3 Customer balance")
        print("4 Today's activity | 5 Activity by date | 6 Truck details | 0 Back")
        choice = input("Choose: ").strip().rstrip(".")

        if choice == "1":
            customer = find_customer()
            if customer:
                if truck.serve_deposit(customer, ask_amount("Amount received: ")):
                    bank.save_accounts()
                    dispatcher.save()
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
                print(f"{customer.owner}: balance {customer.get_balance()}")
        elif choice == "4":
            truck.show_daily_activity()
        elif choice == "5":
            day = input("Date YYYY-MM-DD: ").strip()
            try:
                truck.show_daily_activity(day)
            except ValueError:
                print("Use the date format YYYY-MM-DD.")
        elif choice == "6":
            truck.get_details()
        elif choice == "0":
            break
        else:
            print("Invalid choice.")


def main():
    bank.load_accounts()
    dispatcher = Dispatcher.load()
    while True:
        print(f"\n=== {BankAccount.bank_name} ===")
        print("1 Customer banking | 2 Dispatcher | 3 Bank truck terminal | 0 Exit")
        choice = input("Choose: ").strip().rstrip(".")

        if choice == "1":
            bank.main()                         # the customer menu you already have
        elif choice == "2":
            run_menu(dispatcher)
        elif choice == "3":
            truck_terminal(dispatcher)
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()