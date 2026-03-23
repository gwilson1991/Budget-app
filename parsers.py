"""
CSV Parsers for each bank/credit card source.
Standardizes all transaction data into a common format.
"""

import pandas as pd
import re
from datetime import datetime


# ─── VENDOR NAME CLEANING ─────────────────────────────────────────────────

def clean_vendor_name(description):
    """
    Extract a clean, consistent vendor name from a transaction description.
    This is used for the auto-suggest vendor mapping.
    """
    if not description or not isinstance(description, str):
        return ""

    name = description.upper().strip()

    # Remove common prefixes
    prefixes = [
        r"^POS PURCHASE\s+",
        r"^POS PCH CSH BACK\s+",
        r"^POS\s+",
        r"^TERMINAL \d+\s+",
        r"^TERMINAL\s+",
        r"^SQ \*",         # Square payments
        r"^TST\*",         # Toast payments
        r"^SP \*",         # Shopify payments
    ]
    for prefix in prefixes:
        name = re.sub(prefix, "", name)

    # Remove trailing location info (CITY    STATE pattern)
    # e.g., "WINCO FOODS #29 WINCO1  MOSCOW    ID"
    name = re.sub(r"\s{2,}[A-Z]{2,}\s{2,}[A-Z]{2}\s*$", "", name)
    # Also catch "CITY  ST" at the end
    name = re.sub(r"\s{2,}[A-Z][A-Za-z]+\s{2,}[A-Z]{2}\s*$", "", name)

    # Remove 8-digit date strings (e.g., 20260227)
    name = re.sub(r"\b20\d{6}\b", "", name)

    # Remove PAY followed by numbers (payroll reference numbers)
    name = re.sub(r"\s+PAY\s+\d+", "", name)

    # Remove reference codes (alphanumeric strings after lots of whitespace)
    name = re.sub(r"\s{2,}[A-Za-z0-9-]+\s*$", "", name)

    # Remove store/location numbers after #
    name = re.sub(r"\s*#\d+.*$", "", name)

    # Remove trailing numbers and codes
    name = re.sub(r"\s+\d{4,}\s*$", "", name)

    # Remove "AUTOPAY", "PYMT", "CRCARDPMT", "PAYMENT" suffixes
    name = re.sub(r"\s+(AUTOPAY|PYMT|CRCARDPMT|PAYMENT|CRCARDPYMT)\b.*$", "", name)

    # Remove F-codes (like MCDONALD'S F15101)
    name = re.sub(r"\s+[A-Z]\d{4,}\s*$", "", name)

    # Remove L-codes (like KFC L113009)
    name = re.sub(r"\s+L\d{4,}\s*$", "", name)

    # Clean up extra whitespace
    name = re.sub(r"\s+", " ", name).strip()

    # Remove any trailing single characters
    name = re.sub(r"\s+[A-Z]$", "", name)

    return name.strip()


# ─── TRANSACTION TYPE DETECTION ───────────────────────────────────────────

# Keywords that indicate a credit card payment (transfer) in bank transactions
TRANSFER_KEYWORDS = [
    "CAPITAL ONE",
    "CRCARDPMT",
    "CRCARDPYMT",
    "CHASE CREDIT CRD",
    "CHASE CREDIT",
    "CREDIT CRD",
    "AUTOPAY",
]

# Keywords that indicate investment/savings transfers
INVESTMENT_KEYWORDS = [
    "INVESTMENT",
    "SMCAPGRO",
    "LCAP GRW",
]


def detect_type_bank(description, debit, credit):
    """
    Detect transaction type for Columbia Bank transactions.
    Returns: 'income', 'expense', 'transfer', or 'investment'
    """
    desc_upper = (description or "").upper()

    # Credit column has a value = income
    if credit and float(credit) > 0:
        return "income"

    # Check for credit card payments (transfers to exclude)
    for keyword in TRANSFER_KEYWORDS:
        if keyword in desc_upper:
            return "transfer"

    # Check for investment transfers
    for keyword in INVESTMENT_KEYWORDS:
        if keyword in desc_upper:
            return "expense"  # Track as expense (Roth IRA category)

    # Everything else in debit column = expense
    return "expense"


def detect_type_creditcard(debit, credit):
    """
    Detect transaction type for credit card transactions.
    Returns: 'expense' or 'transfer'
    """
    # Credit column has a value = payment received (transfer)
    if credit and str(credit).strip() and float(credit) > 0:
        return "transfer"

    # Debit column = expense
    return "expense"


# ─── COLUMBIA BANK PARSER ─────────────────────────────────────────────────

def parse_columbia_bank(file):
    """
    Parse Columbia Bank CSV export.

    Columns: Account Number, Post Date, Check, Description, Debit, Credit, Status, Balance
    Date format: M/D/YYYY
    """
    df = pd.read_csv(file)

    # Standardize column names
    df.columns = df.columns.str.strip()

    transactions = []
    for _, row in df.iterrows():
        description = str(row.get("Description", "")).strip().strip('"')
        debit = row.get("Debit", "")
        credit = row.get("Credit", "")

        # Parse amount: positive for expenses, positive for income
        if pd.notna(debit) and str(debit).strip():
            amount = abs(float(str(debit).replace(",", "")))
        elif pd.notna(credit) and str(credit).strip():
            amount = abs(float(str(credit).replace(",", "")))
        else:
            continue  # Skip rows with no amount

        # Parse date
        date_str = str(row.get("Post Date", "")).strip()
        try:
            date_obj = datetime.strptime(date_str, "%m/%d/%Y")
        except ValueError:
            try:
                date_obj = datetime.strptime(date_str, "%m/%d/%y")
            except ValueError:
                continue  # Skip unparseable dates

        # Detect type
        txn_type = detect_type_bank(
            description,
            debit if pd.notna(debit) else "",
            credit if pd.notna(credit) else "",
        )

        transactions.append({
            "date": date_obj.strftime("%Y-%m-%d"),
            "description": description,
            "amount": amount,
            "account": "Columbia Bank",
            "type": txn_type,
            "month": date_obj.strftime("%Y-%m"),
            "vendor_clean": clean_vendor_name(description),
            "bank_hint": "",
        })

    return pd.DataFrame(transactions)


# ─── CAPITOL ONE PARSER ──────────────────────────────────────────────────

def parse_capitol_one(file):
    """
    Parse Capitol One credit card CSV export.

    Columns: Transaction Date, Posted Date, Card No., Description, Category, Debit, Credit
    Date format: YYYY-MM-DD
    """
    df = pd.read_csv(file)
    df.columns = df.columns.str.strip()

    transactions = []
    for _, row in df.iterrows():
        description = str(row.get("Description", "")).strip()
        debit = row.get("Debit", "")
        credit = row.get("Credit", "")
        bank_category = str(row.get("Category", "")).strip()

        # Parse amount
        if pd.notna(debit) and str(debit).strip():
            amount = abs(float(str(debit).replace(",", "")))
        elif pd.notna(credit) and str(credit).strip():
            amount = abs(float(str(credit).replace(",", "")))
        else:
            continue

        # Parse date (use Transaction Date, not Posted Date)
        date_str = str(row.get("Transaction Date", "")).strip()
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue

        # Detect type
        txn_type = detect_type_creditcard(
            debit if pd.notna(debit) else "",
            credit if pd.notna(credit) else "",
        )

        transactions.append({
            "date": date_obj.strftime("%Y-%m-%d"),
            "description": description,
            "amount": amount,
            "account": "Capitol One",
            "type": txn_type,
            "month": date_obj.strftime("%Y-%m"),
            "vendor_clean": clean_vendor_name(description),
            "bank_hint": bank_category if bank_category != "nan" else "",
        })

    return pd.DataFrame(transactions)


# ─── CHASE PARSER ─────────────────────────────────────────────────────────

def parse_chase(file):
    """
    Parse Chase credit card CSV export (Amazon Prime card).

    Columns: Transaction Date, Post Date, Description, Category, Type, Amount, Memo
    Date format: MM/DD/YYYY
    Amount: negative = expense/sale, positive = payment/return
    Type: "Sale" = expense, "Payment" = transfer, "Return" = negative expense (refund)
    """
    df = pd.read_csv(file)
    df.columns = df.columns.str.strip()

    transactions = []
    for _, row in df.iterrows():
        description = str(row.get("Description", "")).strip()
        chase_type = str(row.get("Type", "")).strip()
        bank_category = str(row.get("Category", "")).strip()

        # Parse amount — Chase uses a single column (negative = expense)
        raw_amount = row.get("Amount", 0)
        if pd.isna(raw_amount) or str(raw_amount).strip() == "":
            continue
        raw_amount = float(str(raw_amount).replace(",", ""))
        amount = abs(raw_amount)

        # Determine transaction type
        if chase_type == "Payment":
            txn_type = "transfer"
        elif chase_type == "Return":
            # Returns are negative expenses — they reduce spending in a category
            # Store as negative amount with type "expense" so budget math works
            txn_type = "expense"
            amount = -abs(raw_amount)  # Negative expense = refund
        else:
            # Sale or anything else = expense
            txn_type = "expense"

        # Parse date (use Transaction Date, not Post Date)
        date_str = str(row.get("Transaction Date", "")).strip()
        try:
            date_obj = datetime.strptime(date_str, "%m/%d/%Y")
        except ValueError:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue

        transactions.append({
            "date": date_obj.strftime("%Y-%m-%d"),
            "description": description,
            "amount": amount,
            "account": "Chase",
            "type": txn_type,
            "month": date_obj.strftime("%Y-%m"),
            "vendor_clean": clean_vendor_name(description),
            "bank_hint": bank_category if bank_category != "nan" else "",
        })

    return pd.DataFrame(transactions)


# ─── PARSER ROUTER ────────────────────────────────────────────────────────

PARSERS = {
    "Columbia Bank": parse_columbia_bank,
    "Capitol One": parse_capitol_one,
    "Chase": parse_chase,
}


def parse_csv(file, account_name):
    """Route to the correct parser based on account name."""
    parser = PARSERS.get(account_name)
    if not parser:
        raise ValueError(f"Unknown account: {account_name}")
    return parser(file)
