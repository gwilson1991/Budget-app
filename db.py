"""
Google Sheets database layer for the Budget App.
Handles all read/write operations to the spreadsheet.
"""

import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
from datetime import datetime
import pandas as pd

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Tab names
TAB_CATEGORIES = "Categories"
TAB_BUDGET = "Budget"
TAB_TRANSACTIONS = "Transactions"
TAB_VENDOR_MAP = "Vendor Map"
TAB_SETTINGS = "Settings"

# Default category structure
DEFAULT_CATEGORIES = {
    "Fixed Bills": [
        "Rent", "Utilities", "Car Insurance",
        "Story Family Medicine", "Roth IRA", "Cellphone",
    ],
    "Monthly Variables": [
        "Groceries", "Gas", "Toiletries", "Cleaning Supplies",
        "Tobacco", "Liquor", "Schooling",
    ],
    "Subscriptions": ["Amazon Prime", "Spotify", "Google Drive"],
    "Long Term": [
        "Vacation", "Business", "Emergency Fund", "Baby", "Projects",
    ],
    "Yearly Expenses": [
        "Life Expenditures", "Taxes", "Eye Care", "Dental", "Health",
        "Christmas", "Abi's Christmas", "Gunn's Christmas", "Auto Maintenance",
    ],
    "For Others": [
        "Charity", "Parties", "Lawrence", "Beverly", "Gifts/Birthdays",
    ],
    "Comfort": [
        "Dining Out", "Hair Maintenance", "Clothing",
        "Household Item", "Furniture",
    ],
    "Opulence": ["Electronics", "Gunn", "Abi", "Entertainment"],
}

DEFAULT_GROUP_ORDER = [
    "Fixed Bills", "Monthly Variables", "Subscriptions", "Long Term",
    "Yearly Expenses", "For Others", "Comfort", "Opulence",
]


def get_spreadsheet():
    """Get authenticated connection to the budget spreadsheet."""
    creds_info = dict(st.secrets["gcp_service_account"])
    if "private_key" in creds_info:
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(st.secrets["spreadsheet_id"])


def initialize_sheets(spreadsheet):
    """Create all required tabs with headers if they don't exist."""
    existing_tabs = [ws.title for ws in spreadsheet.worksheets()]

    if TAB_CATEGORIES not in existing_tabs:
        ws = spreadsheet.add_worksheet(title=TAB_CATEGORIES, rows=100, cols=4)
        ws.update("A1:D1", [["group_name", "category_name", "group_order", "category_order"]])
        rows = []
        for g_idx, group in enumerate(DEFAULT_GROUP_ORDER):
            for c_idx, cat in enumerate(DEFAULT_CATEGORIES[group]):
                rows.append([group, cat, g_idx, c_idx])
        if rows:
            ws.update(f"A2:D{len(rows) + 1}", rows)

    if TAB_BUDGET not in existing_tabs:
        ws = spreadsheet.add_worksheet(title=TAB_BUDGET, rows=1000, cols=3)
        ws.update("A1:C1", [["month", "category_name", "budgeted"]])

    if TAB_TRANSACTIONS not in existing_tabs:
        ws = spreadsheet.add_worksheet(title=TAB_TRANSACTIONS, rows=5000, cols=9)
        ws.update("A1:I1", [[
            "date", "description", "amount", "account",
            "category", "type", "month", "upload_id", "bank_hint",
        ]])

    if TAB_VENDOR_MAP not in existing_tabs:
        ws = spreadsheet.add_worksheet(title=TAB_VENDOR_MAP, rows=500, cols=2)
        ws.update("A1:B1", [["vendor_clean", "category"]])

    if TAB_SETTINGS not in existing_tabs:
        ws = spreadsheet.add_worksheet(title=TAB_SETTINGS, rows=20, cols=2)
        ws.update("A1:B1", [["key", "value"]])

    if "Sheet1" in existing_tabs and len(spreadsheet.worksheets()) > 1:
        try:
            spreadsheet.del_worksheet(spreadsheet.worksheet("Sheet1"))
        except Exception:
            pass


# ─── CATEGORIES ────────────────────────────────────────────────────────────

def get_categories(spreadsheet):
    """Returns an ordered dict: {group_name: [category_names]}"""
    ws = spreadsheet.worksheet(TAB_CATEGORIES)
    records = ws.get_all_records()
    if not records:
        return {}

    records.sort(key=lambda r: (int(r.get("group_order", 0)), int(r.get("category_order", 0))))

    from collections import OrderedDict
    categories = OrderedDict()
    for row in records:
        group = row["group_name"]
        cat = row["category_name"]
        if group not in categories:
            categories[group] = []
        categories[group].append(cat)
    return categories


def get_all_category_names(spreadsheet):
    """Returns a flat list of all category names."""
    cats = get_categories(spreadsheet)
    return [c for group_cats in cats.values() for c in group_cats]


def add_category(spreadsheet, group_name, category_name):
    ws = spreadsheet.worksheet(TAB_CATEGORIES)
    records = ws.get_all_records()
    max_order = -1
    group_order = 0
    for r in records:
        if r["group_name"] == group_name:
            group_order = int(r.get("group_order", 0))
            max_order = max(max_order, int(r.get("category_order", 0)))
    ws.append_row([group_name, category_name, group_order, max_order + 1],
                  value_input_option="USER_ENTERED")


def delete_category(spreadsheet, group_name, category_name):
    ws = spreadsheet.worksheet(TAB_CATEGORIES)
    records = ws.get_all_records()
    for i, r in enumerate(records):
        if r["group_name"] == group_name and r["category_name"] == category_name:
            ws.delete_rows(i + 2)
            break


def rename_category(spreadsheet, group_name, old_name, new_name):
    ws = spreadsheet.worksheet(TAB_CATEGORIES)
    records = ws.get_all_records()
    for i, r in enumerate(records):
        if r["group_name"] == group_name and r["category_name"] == old_name:
            ws.update_cell(i + 2, 2, new_name)
            break
    _rename_in_tab(spreadsheet, TAB_BUDGET, "category_name", old_name, new_name)
    _rename_in_tab(spreadsheet, TAB_TRANSACTIONS, "category", old_name, new_name)


def add_group(spreadsheet, group_name):
    ws = spreadsheet.worksheet(TAB_CATEGORIES)
    records = ws.get_all_records()
    max_group_order = max((int(r.get("group_order", 0)) for r in records), default=-1)
    return max_group_order + 1


def delete_group(spreadsheet, group_name):
    ws = spreadsheet.worksheet(TAB_CATEGORIES)
    records = ws.get_all_records()
    rows_to_delete = []
    for i, r in enumerate(records):
        if r["group_name"] == group_name:
            rows_to_delete.append(i + 2)
    for row_num in sorted(rows_to_delete, reverse=True):
        ws.delete_rows(row_num)


def rename_group(spreadsheet, old_name, new_name):
    ws = spreadsheet.worksheet(TAB_CATEGORIES)
    records = ws.get_all_records()
    for i, r in enumerate(records):
        if r["group_name"] == old_name:
            ws.update_cell(i + 2, 1, new_name)


def _rename_in_tab(spreadsheet, tab_name, column_name, old_value, new_value):
    try:
        ws = spreadsheet.worksheet(tab_name)
        records = ws.get_all_records()
        headers = ws.row_values(1)
        col_idx = headers.index(column_name) + 1
        for i, r in enumerate(records):
            if r.get(column_name) == old_value:
                ws.update_cell(i + 2, col_idx, new_value)
    except Exception:
        pass


# ─── BUDGET ────────────────────────────────────────────────────────────────

def get_budget_for_month(spreadsheet, month_str):
    ws = spreadsheet.worksheet(TAB_BUDGET)
    records = ws.get_all_records()
    budget = {}
    for r in records:
        if r["month"] == month_str:
            budget[r["category_name"]] = float(r["budgeted"] or 0)
    return budget


def get_all_budgets_through_month(spreadsheet, month_str):
    ws = spreadsheet.worksheet(TAB_BUDGET)
    records = ws.get_all_records()
    totals = {}
    for r in records:
        if r["month"] <= month_str:
            cat = r["category_name"]
            totals[cat] = totals.get(cat, 0) + float(r["budgeted"] or 0)
    return totals


def set_budget(spreadsheet, month_str, category_name, amount):
    ws = spreadsheet.worksheet(TAB_BUDGET)
    records = ws.get_all_records()
    for i, r in enumerate(records):
        if r["month"] == month_str and r["category_name"] == category_name:
            ws.update_cell(i + 2, 3, amount)
            return
    ws.append_row([month_str, category_name, amount], value_input_option="USER_ENTERED")


def get_total_budgeted_through_month(spreadsheet, month_str):
    totals = get_all_budgets_through_month(spreadsheet, month_str)
    return sum(totals.values())


# ─── TRANSACTIONS ──────────────────────────────────────────────────────────

def get_all_transactions(spreadsheet):
    """Get all transactions as a list of dicts."""
    ws = spreadsheet.worksheet(TAB_TRANSACTIONS)
    return ws.get_all_records()


def get_existing_transaction_keys(spreadsheet):
    """
    Get a set of dedup keys for all existing transactions.
    Key: "date|amount|description|account"
    """
    records = get_all_transactions(spreadsheet)
    keys = set()
    for r in records:
        key = f"{r.get('date', '')}|{r.get('amount', '')}|{r.get('description', '')}|{r.get('account', '')}"
        keys.add(key)
    return keys


def save_transactions(spreadsheet, transactions_df):
    """
    Bulk save transactions to the Transactions tab.
    Expects columns: date, description, amount, account, category, type, month, upload_id, bank_hint
    """
    if transactions_df.empty:
        return

    ws = spreadsheet.worksheet(TAB_TRANSACTIONS)
    rows = []
    for _, row in transactions_df.iterrows():
        rows.append([
            str(row.get("date", "")),
            str(row.get("description", "")),
            float(row.get("amount", 0)),
            str(row.get("account", "")),
            str(row.get("category", "")),
            str(row.get("type", "")),
            str(row.get("month", "")),
            str(row.get("upload_id", "")),
            str(row.get("bank_hint", "")),
        ])

    if rows:
        ws.append_rows(rows, value_input_option="USER_ENTERED")


def update_transaction_category(spreadsheet, row_index, new_category):
    """Update the category of a specific transaction (0-based index)."""
    ws = spreadsheet.worksheet(TAB_TRANSACTIONS)
    ws.update_cell(row_index + 2, 5, new_category)


def get_spending_through_month(spreadsheet, month_str):
    ws = spreadsheet.worksheet(TAB_TRANSACTIONS)
    records = ws.get_all_records()
    totals = {}
    for r in records:
        if r.get("month", "") <= month_str and r.get("type") == "expense":
            cat = r.get("category", "")
            if cat:
                totals[cat] = totals.get(cat, 0) + abs(float(r.get("amount", 0)))
    return totals


def get_spending_for_month(spreadsheet, month_str):
    ws = spreadsheet.worksheet(TAB_TRANSACTIONS)
    records = ws.get_all_records()
    totals = {}
    for r in records:
        if r.get("month", "") == month_str and r.get("type") == "expense":
            cat = r.get("category", "")
            if cat:
                totals[cat] = totals.get(cat, 0) + abs(float(r.get("amount", 0)))
    return totals


def get_total_income_through_month(spreadsheet, month_str):
    ws = spreadsheet.worksheet(TAB_TRANSACTIONS)
    records = ws.get_all_records()
    total = 0
    for r in records:
        if r.get("month", "") <= month_str and r.get("type") == "income":
            total += abs(float(r.get("amount", 0)))
    return total


def get_income_for_month(spreadsheet, month_str):
    ws = spreadsheet.worksheet(TAB_TRANSACTIONS)
    records = ws.get_all_records()
    total = 0
    for r in records:
        if r.get("month", "") == month_str and r.get("type") == "income":
            total += abs(float(r.get("amount", 0)))
    return total


# ─── VENDOR MAP ────────────────────────────────────────────────────────────

def get_vendor_map(spreadsheet):
    """Get vendor-to-category mapping as a dict."""
    ws = spreadsheet.worksheet(TAB_VENDOR_MAP)
    records = ws.get_all_records()
    return {r["vendor_clean"]: r["category"] for r in records if r.get("vendor_clean")}


def update_vendor_map(spreadsheet, vendor_clean, category):
    """Add or update a single vendor mapping."""
    if not vendor_clean or not category:
        return
    ws = spreadsheet.worksheet(TAB_VENDOR_MAP)
    records = ws.get_all_records()
    for i, r in enumerate(records):
        if r.get("vendor_clean", "").upper() == vendor_clean.upper():
            ws.update_cell(i + 2, 2, category)
            return
    ws.append_row([vendor_clean, category], value_input_option="USER_ENTERED")


def bulk_update_vendor_map(spreadsheet, mappings):
    """Update multiple vendor mappings. mappings: list of (vendor_clean, category) tuples."""
    if not mappings:
        return
    ws = spreadsheet.worksheet(TAB_VENDOR_MAP)
    records = ws.get_all_records()
    existing = {r.get("vendor_clean", "").upper(): i for i, r in enumerate(records)}

    new_rows = []
    for vendor, category in mappings:
        if not vendor or not category:
            continue
        if vendor.upper() in existing:
            row_idx = existing[vendor.upper()]
            ws.update_cell(row_idx + 2, 2, category)
        else:
            new_rows.append([vendor, category])
            existing[vendor.upper()] = len(records) + len(new_rows)

    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")


# ─── SETTINGS ──────────────────────────────────────────────────────────────

def get_setting(spreadsheet, key, default=None):
    ws = spreadsheet.worksheet(TAB_SETTINGS)
    records = ws.get_all_records()
    for r in records:
        if r["key"] == key:
            return r["value"]
    return default


def set_setting(spreadsheet, key, value):
    ws = spreadsheet.worksheet(TAB_SETTINGS)
    records = ws.get_all_records()
    for i, r in enumerate(records):
        if r["key"] == key:
            ws.update_cell(i + 2, 2, value)
            return
    ws.append_row([key, value], value_input_option="USER_ENTERED")
