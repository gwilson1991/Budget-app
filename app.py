"""
Personal Budget App — Phase 1
Budget view with manual allocation, category management, and rolling balances.
"""

import streamlit as st
import db
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd

# ─── PAGE CONFIG ───────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Budget App",
    page_icon="💰",
    layout="wide",
)

# ─── AUTHENTICATION ────────────────────────────────────────────────────────

def check_password():
    """Simple password gate. Returns True if authenticated."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("💰 Budget App")
    password = st.text_input("Enter password", type="password")
    if st.button("Log in"):
        if password == st.secrets["app_password"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not check_password():
    st.stop()


# ─── INITIALIZATION ───────────────────────────────────────────────────────

@st.cache_resource
def get_spreadsheet():
    """Get spreadsheet connection (cached so we don't re-auth every rerun)."""
    spreadsheet = db.get_spreadsheet()
    db.initialize_sheets(spreadsheet)
    return spreadsheet


spreadsheet = get_spreadsheet()


def load_data():
    """Load all data from Google Sheets into session state."""
    ss = st.session_state
    ss["categories"] = db.get_categories(spreadsheet)
    month_str = ss.get("current_month", datetime.now().strftime("%Y-%m"))
    ss["budget_this_month"] = db.get_budget_for_month(spreadsheet, month_str)
    ss["cumulative_budgets"] = db.get_all_budgets_through_month(spreadsheet, month_str)
    ss["spending_this_month"] = db.get_spending_for_month(spreadsheet, month_str)
    ss["cumulative_spending"] = db.get_spending_through_month(spreadsheet, month_str)
    ss["income_this_month"] = db.get_income_for_month(spreadsheet, month_str)
    ss["total_income"] = db.get_total_income_through_month(spreadsheet, month_str)
    starting_balance = db.get_setting(spreadsheet, "starting_balance", "0")
    ss["starting_balance"] = float(starting_balance)
    ss["total_budgeted"] = db.get_total_budgeted_through_month(spreadsheet, month_str)
    ss["data_loaded"] = True


# Initialize current month
if "current_month" not in st.session_state:
    st.session_state.current_month = datetime.now().strftime("%Y-%m")

# Load data on first run or when refresh is needed
if "data_loaded" not in st.session_state or st.session_state.get("needs_refresh"):
    load_data()
    st.session_state.needs_refresh = False


# ─── SIDEBAR ──────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("💰 Budget App")
    page = st.radio(
        "Navigate",
        ["Budget", "Upload & Categorize", "Transactions", "Settings"],
        label_visibility="collapsed",
    )
    st.divider()
    if st.button("🔄 Refresh Data", use_container_width=True):
        load_data()
        st.rerun()
    st.caption("Phase 2: Upload & Categorize")
    st.caption("Phase 3: Transactions")


# ─── HELPER FUNCTIONS ─────────────────────────────────────────────────────

def format_currency(amount):
    """Format a number as currency."""
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"


def month_display(month_str):
    """Convert YYYY-MM to a display string like 'March 2026'."""
    dt = datetime.strptime(month_str, "%Y-%m")
    return dt.strftime("%B %Y")


def navigate_month(direction):
    """Move current month forward or backward."""
    dt = datetime.strptime(st.session_state.current_month, "%Y-%m")
    if direction == "prev":
        dt = dt - relativedelta(months=1)
    else:
        dt = dt + relativedelta(months=1)
    st.session_state.current_month = dt.strftime("%Y-%m")
    st.session_state.needs_refresh = True


# ─── BUDGET VIEW ──────────────────────────────────────────────────────────

def render_budget_view():
    """Main budget view with month navigation and category allocation."""
    ss = st.session_state
    month_str = ss["current_month"]

    # ── Month navigation ──
    nav_cols = st.columns([1, 3, 1])
    with nav_cols[0]:
        if st.button("◀ Prev", use_container_width=True):
            navigate_month("prev")
            st.rerun()
    with nav_cols[1]:
        st.markdown(
            f"<h2 style='text-align: center; margin: 0;'>{month_display(month_str)}</h2>",
            unsafe_allow_html=True,
        )
    with nav_cols[2]:
        if st.button("Next ▶", use_container_width=True):
            navigate_month("next")
            st.rerun()

    st.divider()

    # ── Summary metrics ──
    starting_balance = ss["starting_balance"]
    total_income = ss["total_income"]
    total_budgeted = ss["total_budgeted"]
    total_spent = sum(ss["cumulative_spending"].values())
    ready_to_assign = starting_balance + total_income - total_budgeted

    income_this_month = ss["income_this_month"]
    budgeted_this_month = sum(ss["budget_this_month"].values())
    spent_this_month = sum(ss["spending_this_month"].values())

    # Ready to Assign - big and prominent
    rta_color = "#28a745" if ready_to_assign >= 0 else "#dc3545"
    st.markdown(
        f"""
        <div style="text-align: center; padding: 15px; 
                    border-radius: 10px; margin-bottom: 15px;
                    border: 2px solid {rta_color};">
            <div style="font-size: 14px; color: #888;">Ready to Assign</div>
            <div style="font-size: 36px; font-weight: bold; color: {rta_color};">
                {format_currency(ready_to_assign)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Monthly summary
    summary_cols = st.columns(3)
    with summary_cols[0]:
        st.metric("Income This Month", format_currency(income_this_month))
    with summary_cols[1]:
        st.metric("Budgeted This Month", format_currency(budgeted_this_month))
    with summary_cols[2]:
        st.metric("Spent This Month", format_currency(spent_this_month))

    st.divider()

    # ── Category groups with budget allocation ──
    categories = ss["categories"]
    budget_this_month = ss["budget_this_month"]
    cumulative_budgets = ss["cumulative_budgets"]
    spending_this_month = ss["spending_this_month"]
    cumulative_spending = ss["cumulative_spending"]

    if not categories:
        st.info(
            "No categories set up yet. Go to **Settings** to initialize your categories."
        )
        return

    for group_name, cat_list in categories.items():
        with st.expander(f"**{group_name}**", expanded=True):
            # Build a dataframe for this group
            rows = []
            for cat in cat_list:
                budgeted = budget_this_month.get(cat, 0.0)
                spent = spending_this_month.get(cat, 0.0)
                cum_budget = cumulative_budgets.get(cat, 0.0)
                cum_spent = cumulative_spending.get(cat, 0.0)
                available = cum_budget - cum_spent
                rows.append({
                    "Category": cat,
                    "Budgeted": budgeted,
                    "Spent": spent,
                    "Available": available,
                })

            df = pd.DataFrame(rows)

            # Use data_editor for the Budgeted column
            edited_df = st.data_editor(
                df,
                column_config={
                    "Category": st.column_config.TextColumn(
                        "Category", disabled=True, width="medium",
                    ),
                    "Budgeted": st.column_config.NumberColumn(
                        "Budgeted",
                        format="$%.2f",
                        min_value=0,
                        step=5.0,
                        width="small",
                    ),
                    "Spent": st.column_config.NumberColumn(
                        "Spent", format="$%.2f", disabled=True, width="small",
                    ),
                    "Available": st.column_config.NumberColumn(
                        "Available", format="$%.2f", disabled=True, width="small",
                    ),
                },
                hide_index=True,
                use_container_width=True,
                key=f"editor_{group_name}_{month_str}",
            )

            # Detect changes and save them
            for i, row in edited_df.iterrows():
                cat_name = row["Category"]
                new_val = float(row["Budgeted"])
                old_val = float(df.iloc[i]["Budgeted"])
                if new_val != old_val:
                    db.set_budget(spreadsheet, month_str, cat_name, new_val)
                    st.session_state.needs_refresh = True

    # If changes were detected, offer a refresh
    if st.session_state.get("needs_refresh"):
        st.info("Budget updated! Click **Refresh Data** in the sidebar to see updated totals.")


# ─── UPLOAD & CATEGORIZE (Phase 2 placeholder) ───────────────────────────

def render_upload():
    st.header("Upload & Categorize")
    st.info(
        "🚧 **Coming in Phase 2.** This screen will let you upload CSVs from "
        "Columbia Bank, Capitol One, and Chase, review auto-suggested categories, "
        "and confirm transactions."
    )


# ─── TRANSACTIONS (Phase 3 placeholder) ──────────────────────────────────

def render_transactions():
    st.header("Transactions")
    st.info(
        "🚧 **Coming in Phase 3.** This screen will show a searchable, "
        "filterable log of all imported transactions with inline category editing."
    )


# ─── SETTINGS ─────────────────────────────────────────────────────────────

def render_settings():
    st.header("Settings")

    # ── Starting Balance ──
    st.subheader("Starting Balance")
    st.caption(
        "Your bank account balance when you first started using the app. "
        "This becomes your initial 'Ready to Assign' pool."
    )
    current_balance = st.session_state.get("starting_balance", 0)
    new_balance = st.number_input(
        "Starting balance ($)",
        value=float(current_balance),
        min_value=0.0,
        step=100.0,
        format="%.2f",
    )
    if st.button("Save Starting Balance"):
        db.set_setting(spreadsheet, "starting_balance", str(new_balance))
        st.session_state.starting_balance = new_balance
        st.success(f"Starting balance set to {format_currency(new_balance)}")
        st.session_state.needs_refresh = True

    st.divider()

    # ── Category Management ──
    st.subheader("Category Management")
    categories = st.session_state.get("categories", {})

    # Display current categories
    if categories:
        for group_name, cat_list in categories.items():
            with st.expander(f"**{group_name}** ({len(cat_list)} categories)"):
                # Rename group
                col_rg1, col_rg2 = st.columns([3, 1])
                with col_rg1:
                    new_group_name = st.text_input(
                        "Rename group",
                        value=group_name,
                        key=f"rename_group_{group_name}",
                    )
                with col_rg2:
                    st.write("")  # spacing
                    st.write("")
                    if new_group_name != group_name and st.button(
                        "Rename", key=f"btn_rename_group_{group_name}"
                    ):
                        db.rename_group(spreadsheet, group_name, new_group_name)
                        st.success(f"Renamed '{group_name}' to '{new_group_name}'")
                        st.session_state.needs_refresh = True
                        load_data()
                        st.rerun()

                # List categories with delete
                for cat in cat_list:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"  {cat}")
                    with col2:
                        if st.button("🗑️", key=f"del_{group_name}_{cat}",
                                     help=f"Delete {cat}"):
                            db.delete_category(spreadsheet, group_name, cat)
                            st.session_state.needs_refresh = True
                            load_data()
                            st.rerun()

                # Add category to this group
                st.write("")
                col_add1, col_add2 = st.columns([3, 1])
                with col_add1:
                    new_cat = st.text_input(
                        "New category name",
                        key=f"add_cat_{group_name}",
                        placeholder="Enter category name...",
                    )
                with col_add2:
                    st.write("")
                    st.write("")
                    if st.button("Add", key=f"btn_add_{group_name}") and new_cat:
                        if new_cat in cat_list:
                            st.error(f"'{new_cat}' already exists in {group_name}.")
                        else:
                            db.add_category(spreadsheet, group_name, new_cat)
                            st.success(f"Added '{new_cat}' to {group_name}")
                            st.session_state.needs_refresh = True
                            load_data()
                            st.rerun()

                # Delete entire group
                st.write("")
                if st.button(
                    f"🗑️ Delete entire '{group_name}' group",
                    key=f"del_group_{group_name}",
                    type="secondary",
                ):
                    db.delete_group(spreadsheet, group_name)
                    st.warning(f"Deleted group '{group_name}' and all its categories.")
                    st.session_state.needs_refresh = True
                    load_data()
                    st.rerun()
    else:
        st.warning("No categories found. Add a group below to get started.")

    # ── Add New Group ──
    st.divider()
    st.subheader("Add New Group")
    col_ng1, col_ng2, col_ng3 = st.columns([2, 2, 1])
    with col_ng1:
        new_group = st.text_input(
            "Group name", placeholder="e.g., Transportation", key="new_group_name"
        )
    with col_ng2:
        first_cat = st.text_input(
            "First category in this group",
            placeholder="e.g., Bus Pass",
            key="new_group_first_cat",
        )
    with col_ng3:
        st.write("")
        st.write("")
        if st.button("Create Group") and new_group and first_cat:
            if new_group in categories:
                st.error(f"Group '{new_group}' already exists.")
            else:
                group_order = db.add_group(spreadsheet, new_group)
                # Add with the correct group_order
                ws = spreadsheet.worksheet(db.TAB_CATEGORIES)
                ws.append_row(
                    [new_group, first_cat, group_order, 0],
                    value_input_option="USER_ENTERED",
                )
                st.success(f"Created group '{new_group}' with category '{first_cat}'")
                st.session_state.needs_refresh = True
                load_data()
                st.rerun()


# ─── RENDER SELECTED PAGE ────────────────────────────────────────────────

if page == "Budget":
    render_budget_view()
elif page == "Upload & Categorize":
    render_upload()
elif page == "Transactions":
    render_transactions()
elif page == "Settings":
    render_settings()
