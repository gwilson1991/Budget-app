"""
Google Sheets database layer for the Budget App.
Handles all read/write operations to the spreadsheet.
"""

import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
from datetime import datetime

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

# Default group ordering
DEFAULT_GROUP_ORDER = [
    "Fixed Bills", "Monthly Variables", "Subscriptions", "Long Term",
    "Yearly Expenses", "For Others", "Comfort", "Opulence",
]


def get_spreadsheet():
    """Get authenticated connection to the budget spreadsheet."""
    creds_info = dict(st.secrets["gcp_service_account"])
    # gspread expects the private_key newlines to be actual newlines
    if "private_key" in creds_info:
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(st.secrets["spreadsheet_id"])


def initialize_sheets(spreadsheet):
    """
    Create all required tabs with headers if they don't exist.
    Populate default categories on first run.
    """
    existing_tabs = [ws.title for ws in spreadsheet.worksheets()]

    # --- Categories tab ---
    if TAB_CATEGORIES not in existing_tabs:
        ws = spreadsheet.add_worksheet(title=TAB_CATEGORIES, rows=100, cols=4)
        ws.update("A1:D1", [["group_name", "category_name", "group_order", "category_order"]])
        # Populate default categories
        rows = []
        for g_idx, group in enumerate(DEFAULT_GROUP_ORDER):
            for c_idx, cat in enumerate(DEFAULT_CATEGORIES[group]):
                rows.append([group, cat, g_idx, c_idx])
        if rows:
            ws.update(f"A2:D{len(rows) + 1}", rows)
    
    # --- Budget tab ---
    if TAB_BUDGET not in existing_tabs:
        ws = spreadsheet.add_worksheet(title=TAB_BUDGET, rows=1000, cols=3)
        ws.update("A1:C1", [["month", "category_name", "budgeted"]])

    # --- Transactions tab ---
    if TAB_TRANSACTIONS not in existing_tabs:
        ws = spreadsheet.add_worksheet(title=TAB_TRANSACTIONS, rows=5000, cols=9)
        ws.update("A1:I1", [[
            "date", "description", "amount", "account",
            "category", "type", "month", "upload_id", "bank_hint",
        ]])

    # --- Vendor Map tab ---
    if TAB_VENDOR_MAP not in existing_tabs:
        ws = spreadsheet.add_worksheet(title=TAB_VENDOR_MAP, rows=500, cols=2)
        ws.update("A1:B1", [["vendor_clean", "category"]])

    # --- Settings tab ---
    if TAB_SETTINGS not in existing_tabs:
        ws = spreadsheet.add_worksheet(title=TAB_SETTINGS, rows=20, cols=2)
        ws.update("A1:B1", [["key", "value"]])

    # Remove the default "Sheet1" if our tabs were just created
    if "Sheet1" in existing_tabs and len(spreadsheet.worksheets()) > 1:
        try:
            spreadsheet.del_worksheet(spreadsheet.worksheet("Sheet1"))
        except Exception:
            pass


# ─── CATEGORIES ────────────────────────────────────────────────────────────

def get_categories(spreadsheet):
    """
    Returns an ordered dict: {group_name: [category_names]}
    Sorted by group_order, then category_order.
    """
    ws = spreadsheet.worksheet(TAB_CATEGORIES)
    records = ws.get_all_records()
    if not records:
        return {}

    # Sort by group_order then category_order
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
    """Add a new category to an existing group."""
    ws = spreadsheet.worksheet(TAB_CATEGORIES)
    records = ws.get_all_records()

    # Find the max category_order in this group
    max_order = -1
    group_order = 0
    for r in records:
        if r["group_name"] == group_name:
            group_order = int(r.get("group_order", 0))
            max_order = max(max_order, int(r.get("category_order", 0)))

    new_row = [group_name, category_name, group_order, max_order + 1]
    ws.append_row(new_row, value_input_option="USER_ENTERED")


def delete_category(spreadsheet, group_name, category_name):
    """Delete a category. Also cleans up budget entries for it."""
    ws = spreadsheet.worksheet(TAB_CATEGORIES)
    records = ws.get_all_records()

    # Find and delete the row (records are 0-indexed, sheet rows are 1-indexed + header)
    for i, r in enumerate(records):
        if r["group_name"] == group_name and r["category_name"] == category_name:
            ws.delete_rows(i + 2)  # +2 for header row and 1-indexing
            break


def rename_category(spreadsheet, group_name, old_name, new_name):
    """Rename a category. Also updates budget and transaction references."""
    ws = spreadsheet.worksheet(TAB_CATEGORIES)
    records = ws.get_all_records()

    for i, r in enumerate(records):
        if r["group_name"] == group_name and r["category_name"] == old_name:
            ws.update_cell(i + 2, 2, new_name)  # Column B = category_name
            break

    # Update budget tab references
    _rename_in_tab(spreadsheet, TAB_BUDGET, "category_name", old_name, new_name)
    # Update transaction tab references
    _rename_in_tab(spreadsheet, TAB_TRANSACTIONS, "category", old_name, new_name)


def add_group(spreadsheet, group_name):
    """Add a new empty group (it will appear once a category is added to it)."""
    ws = spreadsheet.worksheet(TAB_CATEGORIES)
    records = ws.get_all_records()
    max_group_order = max((int(r.get("group_order", 0)) for r in records), default=-1)
    # We need at least one category to show the group; add a placeholder note
    # Actually, just return the next group order - caller should add a category right after
    return max_group_order + 1


def delete_group(spreadsheet, group_name):
    """Delete an entire group and all its categories."""
    ws = spreadsheet.worksheet(TAB_CATEGORIES)
    records = ws.get_all_records()

    # Find rows to delete (go in reverse to maintain indices)
    rows_to_delete = []
    for i, r in enumerate(records):
        if r["group_name"] == group_name:
            rows_to_delete.append(i + 2)

    for row_num in sorted(rows_to_delete, reverse=True):
        ws.delete_rows(row_num)


def rename_group(spreadsheet, old_name, new_name):
    """Rename a category group."""
    ws = spreadsheet.worksheet(TAB_CATEGORIES)
    records = ws.get_all_records()

    for i, r in enumerate(records):
        if r["group_name"] == old_name:
            ws.update_cell(i + 2, 1, new_name)  # Column A = group_name


def _rename_in_tab(spreadsheet, tab_name, column_name, old_value, new_value):
    """Helper to rename values in a specific column of a tab."""
    try:
        ws = spreadsheet.worksheet(tab_name)
        records = ws.get_all_records()
        headers = ws.row_values(1)
        col_idx = headers.index(column_name) + 1  # 1-indexed

        for i, r in enumerate(records):
            if r.get(column_name) == old_value:
                ws.update_cell(i + 2, col_idx, new_value)
    except Exception:
        pass


# ─── BUDGET ────────────────────────────────────────────────────────────────

def get_budget_for_month(spreadsheet, month_str):
    """
    Get budget allocations for a specific month.
    Returns dict: {category_name: budgeted_amount}
    month_str format: "YYYY-MM"
    """
    ws = spreadsheet.worksheet(TAB_BUDGET)
    records = ws.get_all_records()

    budget = {}
    for r in records:
        if r["month"] == month_str:
            budget[r["category_name"]] = float(r["budgeted"] or 0)
    return budget


def get_all_budgets_through_month(spreadsheet, month_str):
    """
    Get cumulative budgeted amounts for all categories,
    from the beginning of time through the given month.
    Returns dict: {category_name: total_budgeted}
    """
    ws = spreadsheet.worksheet(TAB_BUDGET)
    records = ws.get_all_records()

    totals = {}
    for r in records:
        if r["month"] <= month_str:
            cat = r["category_name"]
            totals[cat] = totals.get(cat, 0) + float(r["budgeted"] or 0)
    return totals


def set_budget(spreadsheet, month_str, category_name, amount):
    """
    Set the budgeted amount for a category in a specific month.
    Creates the row if it doesn't exist, updates if it does.
    """
    ws = spreadsheet.worksheet(TAB_BUDGET)
    records = ws.get_all_records()

    # Check if row already exists
    for i, r in enumerate(records):
        if r["month"] == month_str and r["category_name"] == category_name:
            ws.update_cell(i + 2, 3, amount)  # Column C = budgeted
            return

    # Row doesn't exist, append it
    ws.append_row(
        [month_str, category_name, amount],
        value_input_option="USER_ENTERED",
    )


def get_total_budgeted_through_month(spreadsheet, month_str):
    """Get the total amount budgeted across ALL categories through a given month."""
    totals = get_all_budgets_through_month(spreadsheet, month_str)
    return sum(totals.values())


# ─── TRANSACTIONS (Phase 2 prep, minimal for now) ─────────────────────────

def get_spending_through_month(spreadsheet, month_str):
    """
    Get cumulative spending per category through the given month.
    Returns dict: {category_name: total_spent}
    """
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
    """
    Get spending per category for a specific month.
    Returns dict: {category_name: spent_amount}
    """
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
    """Get total income from all transactions through the given month."""
    ws = spreadsheet.worksheet(TAB_TRANSACTIONS)
    records = ws.get_all_records()

    total = 0
    for r in records:
        if r.get("month", "") <= month_str and r.get("type") == "income":
            total += abs(float(r.get("amount", 0)))
    return total


def get_income_for_month(spreadsheet, month_str):
    """Get total income for a specific month."""
    ws = spreadsheet.worksheet(TAB_TRANSACTIONS)
    records = ws.get_all_records()

    total = 0
    for r in records:
        if r.get("month", "") == month_str and r.get("type") == "income":
            total += abs(float(r.get("amount", 0)))
    return total


# ─── SETTINGS ──────────────────────────────────────────────────────────────

def get_setting(spreadsheet, key, default=None):
    """Get a setting value by key."""
    ws = spreadsheet.worksheet(TAB_SETTINGS)
    records = ws.get_all_records()
    for r in records:
        if r["key"] == key:
            return r["value"]
    return default


def set_setting(spreadsheet, key, value):
    """Set a setting value. Creates it if it doesn't exist."""
    ws = spreadsheet.worksheet(TAB_SETTINGS)
    records = ws.get_all_records()

    for i, r in enumerate(records):
        if r["key"] == key:
            ws.update_cell(i + 2, 2, value)  # Column B = value
            return

    ws.append_row([key, value], value_input_option="USER_ENTERED")
