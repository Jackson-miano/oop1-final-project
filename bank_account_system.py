"""
=====================================================================
 MODULE 1 of 4  -  bank_account_system.py
=====================================================================
ROLE
    The BASE module. It holds the BankAccount class (every account in
    the system is built from it) and the customer register / log-in menu.

HOW THE 4 MODULES FIT TOGETHER
    bank_account_system.py   <- YOU ARE HERE  (base class BankAccount)
              ^
    bank_truck.py            <- BankTruck INHERITS from BankAccount
              ^
    dispatcher.py            <- Dispatcher manages the BankTruck objects
              ^
    bank_main.py             <- the ONE file you run (joins all menus)

RUN
    python bank_main.py      (this file can also be run on its own)

DATA
    accounts.json  - customer accounts, saved automatically
=====================================================================
"""

# ---------------------------------------------------------------------
# STEP 1: import the tools we need
#   json  -> saves / loads data as a file
#   math  -> lets us reject impossible numbers (infinity, nan)
#   os    -> finds the folder this file lives in
# ---------------------------------------------------------------------
import json
import math
import os

# ---------------------------------------------------------------------
# STEP 2: decide where customer data is stored.
# The file sits next to this script, so it is found from any folder.
# ---------------------------------------------------------------------
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.json")


# =====================================================================
# STEP 3: THE BankAccount CLASS  (the blueprint for every account)
# =====================================================================
class BankAccount:
    # CLASS ATTRIBUTE: one bank name shared by every account.
    bank_name = "The_Joint_Bank"

    # -----------------------------------------------------------------
    # STEP 3.1: create an account
    # -----------------------------------------------------------------
    def __init__(self, account_number, owner, opening_balance):
        self.account_number = str(account_number)   # unique number / ID (always text)
        self.owner = owner                          # who owns the account
        self.balance = opening_balance              # money in the account now
        self.opening_balance = opening_balance      # first deposit: balance may never go below it
        self.transactions = []                      # history of deposits and withdrawals

    def show_bank_name(self):
        print(f"Bank: {self.bank_name}")

    # -----------------------------------------------------------------
    # STEP 3.2: STATIC METHODS  (helpers that need no account object)
    # -----------------------------------------------------------------
    @staticmethod
    def is_valid_amount(amount):
        """STATIC METHOD: True only for a real number that is at least 0.01."""
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            return False                            # text, None or True/False are not money
        return math.isfinite(amount) and round(amount, 2) > 0

    @staticmethod
    def format_money(amount):
        """STATIC METHOD: 2500 -> '2,500.00' so every amount prints the same way."""
        return f"{amount:,.2f}"

    # -----------------------------------------------------------------
    # STEP 3.3: CLASS METHOD  (works on the class, not on one account)
    # -----------------------------------------------------------------
    @classmethod
    def change_bank_name(cls, new_name):
        """CLASS METHOD: changes the bank name for ALL accounts at once."""
        if str(new_name).strip():
            cls.bank_name = str(new_name).strip()

    # -----------------------------------------------------------------
    # STEP 3.4: deposit.
    # ENCAPSULATION: the balance is only changed here, after the amount
    # has been validated and rounded to cents. Returns True if money moved.
    # -----------------------------------------------------------------
    def deposit(self, amount):
        if not self.is_valid_amount(amount):
            print("Invalid amount.")
            return False
        amount = round(amount, 2)
        self.balance = round(self.balance + amount, 2)
        self.transactions.append(
            f"Deposit: +{self.format_money(amount)} | Balance: {self.format_money(self.balance)}")
        print(f"Deposited {self.format_money(amount)}. "
              f"New balance: {self.format_money(self.balance)}")
        return True

    # -----------------------------------------------------------------
    # STEP 3.5: the withdrawal rule.
    # A withdrawal is refused if it would leave the balance below the
    # opening balance.
    # -----------------------------------------------------------------
    def check_withdrawal(self, amount):
        """Return (True, "") if allowed, otherwise (False, explanation)."""
        if not self.is_valid_amount(amount):
            return False, "Invalid amount."
        amount = round(amount, 2)
        if round(self.balance - amount, 2) < self.opening_balance:
            maximum = max(0, round(self.balance - self.opening_balance, 2))
            return False, (f"You cannot withdraw below the opening balance of "
                           f"{self.format_money(self.opening_balance)}. "
                           f"The most you can withdraw now is {self.format_money(maximum)}.")
        return True, ""

    def withdraw(self, amount):
        """Take money out if the rule allows it. Returns True if money moved."""
        allowed, message = self.check_withdrawal(amount)    # validates AND applies the rule
        if not allowed:
            print(message)
            return False
        amount = round(amount, 2)
        self.balance = round(self.balance - amount, 2)
        self.transactions.append(
            f"Withdrawal: -{self.format_money(amount)} | Balance: {self.format_money(self.balance)}")
        print(f"Withdrew {self.format_money(amount)}. "
              f"New balance: {self.format_money(self.balance)}")
        return True

    def show_withdrawal_notice(self):
        """Tell the customer the rule BEFORE they type an amount."""
        available = max(0, round(self.balance - self.opening_balance, 2))
        print(f"Notice: you cannot withdraw any amount that takes your balance below "
              f"the opening balance of {self.format_money(self.opening_balance)}.")
        print(f"Amount you can withdraw now: {self.format_money(available)}")

    # -----------------------------------------------------------------
    # STEP 3.6: reading information
    # -----------------------------------------------------------------
    def get_balance(self):
        return self.balance

    def get_details(self):
        print("\n--- Account Details ---")
        print("Bank:            ", self.bank_name)
        print("Account number:  ", self.account_number)
        print("Owner:           ", self.owner)
        print("Opening balance: ", self.format_money(self.opening_balance))
        print("Current balance: ", self.format_money(self.balance))

    def show_history(self):
        print("\n--- Transaction History ---")
        if not self.transactions:
            print("No transactions yet.")
            return
        for line in self.transactions:
            print(line)

    # -----------------------------------------------------------------
    # STEP 3.7: saving and loading one account
    # -----------------------------------------------------------------
    def to_dict(self):
        """Turn the account into a plain dictionary so JSON can save it."""
        return {
            "account_number": self.account_number,
            "owner": self.owner,
            "balance": self.balance,
            "opening_balance": self.opening_balance,
            "transactions": self.transactions,
        }

    @classmethod
    def from_dict(cls, data):
        """CLASS METHOD: rebuild an account from saved data."""
        # accounts saved by older versions have no opening balance: use the balance
        opening = data.get("opening_balance", data["balance"])
        account = cls(data["account_number"], data["owner"], opening)
        account.balance = data["balance"]
        account.transactions = data.get("transactions", [])
        return account


# =====================================================================
# STEP 4: STORAGE - all customer accounts live in this dictionary
#         {account_number: BankAccount}
# =====================================================================
accounts = {}


def save_accounts():
    """STEP 4.1: write every account to accounts.json."""
    data = {number: account.to_dict() for number, account in accounts.items()}
    with open(DATA_FILE, "w") as file:
        json.dump(data, file, indent=4)


def load_accounts():
    """STEP 4.2: read accounts.json back into the dictionary."""
    if not os.path.exists(DATA_FILE):
        return                                      # first run: nothing saved yet
    try:
        with open(DATA_FILE, "r") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("Invalid account data.")
        loaded = {}                                 # build everything first...
        for number, details in data.items():
            loaded[str(number)] = BankAccount.from_dict(details)
        accounts.clear()                            # ...then swap it in (all or nothing)
        accounts.update(loaded)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        print("Warning: could not read saved accounts.")


# =====================================================================
# STEP 5: THE CUSTOMER MENU
# =====================================================================
def get_amount(prompt):
    """STEP 5.1: ask for a number; return None if the user typed text."""
    try:
        return float(input(prompt))
    except ValueError:
        return None


def register():
    """STEP 5.2: create a new customer account."""
    number = input("Choose an account number: ").strip()
    if not number:
        print("Account number cannot be empty.")
        return
    if number in accounts:
        print("That account number already exists.")
        return
    owner = input("Owner name: ").strip()
    if not owner:
        print("Owner name cannot be empty.")
        return
    balance = get_amount("Opening balance: ")
    if not BankAccount.is_valid_amount(balance):
        print("Invalid amount. Account not created.")
        return
    accounts[number] = BankAccount(number, owner, round(balance, 2))
    save_accounts()
    print("Account created and saved!")


def account_menu(account):
    """STEP 5.3: what a logged-in customer can do."""
    while True:
        print(f"\n--- {account.owner} ---")
        print("1 Balance | 2 Deposit | 3 Withdraw | 4 Details | 5 History | 6 Delete | 7 Log out")
        choice = input("Choose: ").strip().rstrip(".")

        if choice == "1":
            print(f"Current balance: {account.format_money(account.get_balance())}")
        elif choice == "2":
            if account.deposit(get_amount("Amount to deposit: ")):
                save_accounts()                     # save only when money really moved
        elif choice == "3":
            account.show_withdrawal_notice()
            if account.withdraw(get_amount("Amount to withdraw: ")):
                save_accounts()
        elif choice == "4":
            account.get_details()
        elif choice == "5":
            account.show_history()
        elif choice == "6":
            confirm = input("Type YES to permanently delete this account: ")
            if confirm == "YES":
                del accounts[account.account_number]
                save_accounts()
                print("Account deleted.")
                break
            print("Cancelled.")
        elif choice == "7":
            break
        else:
            print("Invalid choice.")


def customer_menu():
    """STEP 5.4: Register / Log in / Back (used by bank_main.py)."""
    while True:
        print(f"\n=== {BankAccount.bank_name} ===")
        print("1. Register")
        print("2. Log in")
        print("3. Back to main menu")
        choice = input("Choose: ").strip().rstrip(".")

        if choice == "1":
            register()
        elif choice == "2":
            number = input("Enter your account number: ").strip()
            if number in accounts:
                account_menu(accounts[number])
            else:
                print("Account not found.")
        elif choice == "3":
            break
        else:
            print("Invalid choice.")


def main():
    """
    STEP 5.5: run the customer menu when THIS file is started on its own.
    When the customer chooses "Back to main menu", the real main menu
    (bank_main.py) opens, so the option works from here too.
    """
    load_accounts()
    customer_menu()
    # imported here (not at the top) so bank_main.py can import this file without a loop
    from bank_main import main as open_main_menu
    open_main_menu()


# STEP 6: start the menu ONLY when this file is run directly.
# When bank_truck.py or bank_main.py import this file, the menu stays quiet.
if __name__ == "__main__":
    main()
