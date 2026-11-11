
import json
import os
import math

DATA_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "accounts.json"
)


class BankAccount:
    bank_name = "The_Joint_Bank"

    def __init__(self, account_number, owner, opening_balance):
        self.account_number = str(account_number)
        self.owner = owner
        self.balance = opening_balance
        self.opening_balance = opening_balance
        self.transactions = []

    def show_bank_name(self):
        print(f"Bank: {self.bank_name}")

    @staticmethod
    def is_valid_amount(amount):
        return (
            isinstance(amount, (int, float))
            and not isinstance(amount, bool)
            and math.isfinite(amount)
            and amount > 0
        )

    @classmethod
    def change_bank_name(cls, new_name):
        if str(new_name).strip():
            cls.bank_name = str(new_name).strip()

    def deposit(self, amount):
        if not self.is_valid_amount(amount):
            print("Invalid amount.")
            return False

        self.balance += amount
        self.transactions.append(
            f"Deposit: +{amount:.2f} | Balance: {self.balance:.2f}"
        )
        print(f"Deposited {amount:.2f}. New balance: {self.balance:.2f}")
        return True

    def check_withdrawal(self, amount):
        """Return (True, '') if allowed, otherwise (False, message)."""

        if not self.is_valid_amount(amount):
            return False, "Invalid amount."

        if self.balance - amount < self.opening_balance:
            maximum = max(0, self.balance - self.opening_balance)

            return False, (
                f"You cannot withdraw below the opening balance "
                f"of {self.opening_balance:.2f}. "
                f"The most you can withdraw now is {maximum:.2f}."
            )

        return True, ""

    def withdraw(self, amount):
        allowed, message = self.check_withdrawal(amount)

        if not allowed:
            print(message)
            return False

        self.balance -= amount
        self.transactions.append(
            f"Withdrawal: -{amount:.2f} | Balance: {self.balance:.2f}"
        )

        print(f"Withdrew {amount:.2f}. New balance: {self.balance:.2f}")
        return True

    def show_withdrawal_notice(self):
        available = max(0, self.balance - self.opening_balance)

        print(
            f"Notice: you cannot withdraw any amount that takes "
            f"your balance below the opening balance of "
            f"{self.opening_balance:.2f}."
        )
        print(f"Amount you can withdraw now: {available:.2f}")

    def get_balance(self):
        return self.balance

    def get_details(self):
        print("\n--- Account Details ---")
        print("Bank:           ", self.bank_name)
        print("Account number: ", self.account_number)
        print("Owner:          ", self.owner)
        print(f"Opening balance: {self.opening_balance:.2f}")
        print(f"Current balance: {self.balance:.2f}")

    def show_history(self):
        print("\n--- Transaction History ---")

        if not self.transactions:
            print("No transactions yet.")
            return

        for transaction in self.transactions:
            print(transaction)

    def to_dict(self):
        return {
            "account_number": self.account_number,
            "owner": self.owner,
            "balance": self.balance,
            "opening_balance": self.opening_balance,
            "transactions": self.transactions
        }

    @classmethod
    def from_dict(cls, data):
        opening_balance = data.get(
            "opening_balance",
            data["balance"]
        )

        account = cls(
            account_number=data["account_number"],
            owner=data["owner"],
            opening_balance=data.get("opening_balance", data.get("balance", 0.0))
        )
    
        account.balance = data["balance"]
        account.transactions = data.get("transactions", [])

        return account


accounts = {}


def save_accounts():
    data = {
        number: account.to_dict()
        for number, account in accounts.items()
    }

    with open(DATA_FILE, "w") as file:
        json.dump(data, file, indent=4)


def load_accounts():
    if not os.path.exists(DATA_FILE):
        return

    try:
        with open(DATA_FILE, "r") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Invalid account data.")

        loaded = {}

        for number, details in data.items():
            account = BankAccount.from_dict(details)
            loaded[str(number)] = account

        accounts.clear()
        accounts.update(loaded)

    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        print("Warning: could not read saved accounts.")


def get_amount(prompt):
    try:
        return float(input(prompt))
    except ValueError:
        return None


def register():
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

    accounts[number] = BankAccount(number, owner, balance)

    save_accounts()
    print("Account created and saved!")


def account_menu(account):
    while True:
        print(f"\n--- {account.owner} ---")
        print("1. Balance")
        print("2. Deposit")
        print("3. Withdraw")
        print("4. Details")
        print("5. Transaction history")
        print("6. Delete account")
        print("7. Log out")

        choice = input("Choose: ").strip().rstrip(".")

        if choice == "1":
            print(f"Current balance: {account.get_balance():.2f}")

        elif choice == "2":
            amount = get_amount("Amount to deposit: ")

            if account.deposit(amount):
                save_accounts()

        elif choice == "3":
            account.show_withdrawal_notice()
            amount = get_amount("Amount to withdraw: ")

            if account.withdraw(amount):
                save_accounts()

        elif choice == "4":
            account.get_details()

        elif choice == "5":
            account.show_history()

        elif choice == "6":
            confirm = input(
                "Type YES to permanently delete this account: "
            )

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
    """Customer banking menu used by the integrated main program."""

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
    load_accounts()
    customer_menu()


if __name__ == "__main__":
    main()
