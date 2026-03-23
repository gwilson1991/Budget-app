"""
Personal Budget App — Phase 1 + 2 + 3
Budget view, CSV upload, transaction list with search/filter/edit.
"""

import streamlit as st
import db
import parsers
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
import uuid

# ─── PAGE CONFIG ───────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Budget App",
    page_icon="💰",
    layout="wide",
)

# ─── AUTHENTICATION ────────────────────────────────────────────────────────

def check_password():
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
    spreadsheet = db.get_spreadsheet()
    db.initialize_sheets(spreadsheet)
    return spreadsheet


spreadsheet = get_spreadsheet()


def load_data():
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


if "current_month" not in st.session_state:
    st.session_state.current_month = datetime.now().strftime("%Y-%m")

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


# ─── HELPER FUNCTIONS ─────────────────────────────────────────────────────

def format_currency(amount):
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"


def month_display(month_str):
    dt = datetime.strptime(month_str, "%Y-%m")
    return dt.strftime("%B %Y")


def navigate_month(direction):
    dt = datetime.strptime(st.session_state.current_month, "%Y-%m")
    if direction == "prev":
        dt = dt - relativedelta(months=1)
    else:
        dt = dt + relativedelta(months=1)
    st.session_state.current_month = dt.strftime("%Y-%m")
    st.session_state.needs_refresh = True


# ─── BUDGET VIEW ──────────────────────────────────────────────────────────

def render_budget_view():
    ss = st.session_state
    month_str = ss["current_month"]

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

    starting_balance = ss["starting_balance"]
    total_income = ss["total_income"]
    total_budgeted = ss["total_budgeted"]
    ready_to_assign = starting_balance + total_income - total_budgeted

    income_this_month = ss["income_this_month"]
    budgeted_this_month = sum(ss["budget_this_month"].values())
    spent_this_month = sum(ss["spending_this_month"].values())

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

    summary_cols = st.columns(3)
    with summary_cols[0]:
        st.metric("Income This Month", format_currency(income_this_month))
    with summary_cols[1]:
        st.metric("Budgeted This Month", format_currency(budgeted_this_month))
    with summary_cols[2]:
        st.metric("Spent This Month", format_currency(spent_this_month))

    st.divider()

    categories = ss["categories"]
    budget_this_month = ss["budget_this_month"]
    cumulative_budgets = ss["cumulative_budgets"]
    spending_this_month = ss["spending_this_month"]
    cumulative_spending = ss["cumulative_spending"]

    if not categories:
        st.info("No categories set up yet. Go to **Settings** to initialize your categories.")
        return

    for group_name, cat_list in categories.items():
        with st.expander(f"**{group_name}**", expanded=True):
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
            edited_df = st.data_editor(
                df,
                column_config={
                    "Category": st.column_config.TextColumn(
                        "Category", disabled=True, width="medium",
                    ),
                    "Budgeted": st.column_config.NumberColumn(
                        "Budgeted", format="$%.2f", min_value=0, step=5.0, width="small",
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

            for i, row in edited_df.iterrows():
                cat_name = row["Category"]
                new_val = float(row["Budgeted"])
                old_val = float(df.iloc[i]["Budgeted"])
                if new_val != old_val:
                    db.set_budget(spreadsheet, month_str, cat_name, new_val)
                    st.session_state.needs_refresh = True

    if st.session_state.get("needs_refresh"):
        st.info("Budget updated! Click **Refresh Data** in the sidebar to see updated totals.")


# ─── UPLOAD & CATEGORIZE ─────────────────────────────────────────────────

def render_upload():
    st.header("Upload & Categorize")

    # Step 1: Upload
    st.subheader("Step 1: Upload CSV")
    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded_file = st.file_uploader(
            "Choose a CSV file", type=["csv"], key="csv_upload",
        )
    with col2:
        account = st.selectbox(
            "Account source",
            ["Columbia Bank", "Capitol One", "Chase"],
            key="account_source",
        )

    if uploaded_file is not None and st.button("Parse CSV", type="primary"):
        with st.spinner("Parsing transactions..."):
            try:
                parsed_df = parsers.parse_csv(uploaded_file, account)

                if parsed_df.empty:
                    st.warning("No transactions found in this file.")
                    return

                existing_keys = db.get_existing_transaction_keys(spreadsheet)
                upload_id = str(uuid.uuid4())[:8]
                parsed_df["upload_id"] = upload_id

                new_mask = []
                for _, row in parsed_df.iterrows():
                    key = f"{row['date']}|{row['amount']}|{row['description']}|{row['account']}"
                    new_mask.append(key not in existing_keys)

                dupes_count = len(new_mask) - sum(new_mask)
                parsed_df = parsed_df[new_mask].reset_index(drop=True)

                if dupes_count > 0:
                    st.info(f"Skipped **{dupes_count}** duplicate transaction(s).")

                if parsed_df.empty:
                    st.warning("All transactions are duplicates. Nothing new to import.")
                    return

                vendor_map = db.get_vendor_map(spreadsheet)
                suggested_categories = []
                for _, row in parsed_df.iterrows():
                    vendor = row.get("vendor_clean", "")
                    if vendor:
                        match_key = next(
                            (k for k in vendor_map if k.upper() == vendor.upper()), None
                        )
                        suggested_categories.append(
                            vendor_map.get(match_key, "") if match_key else ""
                        )
                    else:
                        suggested_categories.append("")

                parsed_df["suggested_category"] = suggested_categories
                st.session_state["staged_transactions"] = parsed_df
                st.session_state["staged_account"] = account

            except Exception as e:
                st.error(f"Error parsing CSV: {str(e)}")
                return

    # Step 2: Review and categorize
    if "staged_transactions" in st.session_state:
        staged_df = st.session_state["staged_transactions"]

        st.divider()
        st.subheader("Step 2: Review & Categorize")

        all_categories = db.get_all_category_names(spreadsheet)

        expenses = staged_df[staged_df["type"] == "expense"].copy()
        income = staged_df[staged_df["type"] == "income"].copy()
        transfers = staged_df[staged_df["type"] == "transfer"].copy()

        if not income.empty:
            st.markdown("### 💵 Income")
            st.caption("These will be added to your 'Ready to Assign' pool.")
            income_display = income[["date", "description", "amount"]].copy()
            income_display["amount"] = income_display["amount"].apply(lambda x: f"${x:,.2f}")
            st.dataframe(income_display, hide_index=True, use_container_width=True)

        if not transfers.empty:
            st.markdown("### 🔄 Transfers (Excluded)")
            st.caption("Credit card payments — tracked but not counted as spending.")
            transfers_display = transfers[["date", "description", "amount"]].copy()
            transfers_display["amount"] = transfers_display["amount"].apply(lambda x: f"${x:,.2f}")
            st.dataframe(transfers_display, hide_index=True, use_container_width=True)

        if not expenses.empty:
            st.markdown("### 🏷️ Expenses — Assign Categories")

            has_hints = expenses["bank_hint"].any()
            if has_hints:
                st.caption("💡 'Bank Says' shows the bank's own category — for reference only.")

            editor_rows = []
            for idx, row in expenses.iterrows():
                editor_row = {
                    "Date": row["date"],
                    "Description": row["description"],
                    "Amount": row["amount"],
                    "Category": row.get("suggested_category", ""),
                }
                if has_hints:
                    editor_row["Bank Says"] = row.get("bank_hint", "")
                editor_rows.append(editor_row)

            editor_df = pd.DataFrame(editor_rows)

            col_config = {
                "Date": st.column_config.TextColumn("Date", disabled=True, width="small"),
                "Description": st.column_config.TextColumn(
                    "Description", disabled=True, width="large",
                ),
                "Amount": st.column_config.NumberColumn(
                    "Amount", format="$%.2f", disabled=True, width="small",
                ),
                "Category": st.column_config.SelectboxColumn(
                    "Category", options=all_categories, required=False, width="medium",
                ),
            }
            if has_hints:
                col_config["Bank Says"] = st.column_config.TextColumn(
                    "Bank Says", disabled=True, width="small",
                )

            edited_expenses = st.data_editor(
                editor_df, column_config=col_config,
                hide_index=True, use_container_width=True, key="expense_editor",
            )

            st.session_state["edited_expense_categories"] = edited_expenses["Category"].tolist()

            assigned = sum(1 for c in edited_expenses["Category"] if c and str(c).strip())
            total = len(edited_expenses)
            unassigned = total - assigned

            if unassigned > 0:
                st.warning(f"**{unassigned}** of **{total}** expenses still need a category.")
            else:
                st.success(f"All **{total}** expenses are categorized!")

        # Step 3: Save
        st.divider()
        st.subheader("Step 3: Save")

        allow_partial = st.checkbox(
            "Allow saving with uncategorized transactions",
            value=False,
            help="Uncategorized expenses can be assigned later in the Transactions view.",
        )

        can_save = True
        if not expenses.empty:
            edited_cats = st.session_state.get("edited_expense_categories", [])
            if not allow_partial and any(not c or not str(c).strip() for c in edited_cats):
                can_save = False

        if st.button("💾 Save All Transactions", type="primary",
                     disabled=not can_save, use_container_width=True):
            with st.spinner("Saving transactions..."):
                try:
                    all_to_save = []
                    if not income.empty:
                        income_save = income.copy()
                        income_save["category"] = "Income"
                        all_to_save.append(income_save)
                    if not transfers.empty:
                        transfers_save = transfers.copy()
                        transfers_save["category"] = "Transfer"
                        all_to_save.append(transfers_save)
                    if not expenses.empty:
                        edited_cats = st.session_state.get("edited_expense_categories", [])
                        expenses_save = expenses.copy()
                        expenses_save["category"] = edited_cats
                        all_to_save.append(expenses_save)

                    if all_to_save:
                        final_df = pd.concat(all_to_save, ignore_index=True)
                        save_cols = [
                            "date", "description", "amount", "account",
                            "category", "type", "month", "upload_id", "bank_hint",
                        ]
                        db.save_transactions(spreadsheet, final_df[save_cols])

                        if not expenses.empty:
                            vendor_mappings = []
                            for i, (_, row) in enumerate(expenses.iterrows()):
                                cat = edited_cats[i] if i < len(edited_cats) else ""
                                vendor = row.get("vendor_clean", "")
                                if vendor and cat and str(cat).strip():
                                    vendor_mappings.append((vendor, cat))
                            if vendor_mappings:
                                db.bulk_update_vendor_map(spreadsheet, vendor_mappings)

                    for key in ["staged_transactions", "staged_account",
                                "edited_expense_categories"]:
                        st.session_state.pop(key, None)

                    st.session_state.needs_refresh = True
                    st.success(f"Saved **{len(final_df)}** transactions!")
                    st.rerun()

                except Exception as e:
                    st.error(f"Error saving transactions: {str(e)}")

        if st.button("Cancel / Clear", use_container_width=True):
            for key in ["staged_transactions", "staged_account",
                        "edited_expense_categories"]:
                st.session_state.pop(key, None)
            st.rerun()


# ─── TRANSACTIONS ─────────────────────────────────────────────────────────

def render_transactions():
    st.header("Transactions")

    # Load all transactions
    try:
        records = db.get_all_transactions(spreadsheet)
    except Exception:
        records = []

    if not records:
        st.info("No transactions yet. Upload your first CSV in **Upload & Categorize**.")
        return

    df = pd.DataFrame(records)

    # Ensure amount is numeric
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    # ── Filters ──
    st.subheader("Filters")
    filter_cols = st.columns([2, 1, 1, 1])

    with filter_cols[0]:
        search_text = st.text_input(
            "🔍 Search descriptions",
            placeholder="e.g., Winco, Shell, Spotify...",
            key="txn_search",
        )

    with filter_cols[1]:
        # Account filter
        accounts = ["All"] + sorted(df["account"].unique().tolist())
        selected_account = st.selectbox("Account", accounts, key="txn_account_filter")

    with filter_cols[2]:
        # Type filter
        types = ["All"] + sorted(df["type"].unique().tolist())
        selected_type = st.selectbox("Type", types, key="txn_type_filter")

    with filter_cols[3]:
        # Category filter
        all_categories = ["All"] + sorted(
            [c for c in df["category"].unique().tolist() if c and str(c).strip()]
        )
        selected_category = st.selectbox("Category", all_categories, key="txn_cat_filter")

    # Date range filter
    date_cols = st.columns([1, 1, 2])
    with date_cols[0]:
        # Get min/max dates
        df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce")
        min_date = df["date_parsed"].min()
        max_date = df["date_parsed"].max()
        if pd.notna(min_date):
            start_date = st.date_input(
                "From date",
                value=min_date.date(),
                min_value=min_date.date(),
                max_value=max_date.date() if pd.notna(max_date) else None,
                key="txn_start_date",
            )
        else:
            start_date = None

    with date_cols[1]:
        if pd.notna(max_date):
            end_date = st.date_input(
                "To date",
                value=max_date.date(),
                min_value=min_date.date() if pd.notna(min_date) else None,
                max_value=max_date.date(),
                key="txn_end_date",
            )
        else:
            end_date = None

    with date_cols[2]:
        # Month shortcut
        months_available = sorted(df["month"].unique().tolist(), reverse=True)
        month_options = ["All months"] + months_available
        selected_month = st.selectbox("Quick month filter", month_options, key="txn_month_filter")

    # ── Apply filters ──
    filtered = df.copy()

    if search_text:
        filtered = filtered[
            filtered["description"].str.contains(search_text, case=False, na=False)
        ]

    if selected_account != "All":
        filtered = filtered[filtered["account"] == selected_account]

    if selected_type != "All":
        filtered = filtered[filtered["type"] == selected_type]

    if selected_category != "All":
        filtered = filtered[filtered["category"] == selected_category]

    if selected_month != "All months":
        filtered = filtered[filtered["month"] == selected_month]
    else:
        # Apply date range
        if start_date is not None:
            filtered = filtered[filtered["date_parsed"] >= pd.Timestamp(start_date)]
        if end_date is not None:
            filtered = filtered[filtered["date_parsed"] <= pd.Timestamp(end_date)]

    # ── Summary ──
    st.divider()
    summary_cols = st.columns(4)
    with summary_cols[0]:
        st.metric("Transactions", len(filtered))
    with summary_cols[1]:
        expense_total = filtered[filtered["type"] == "expense"]["amount"].sum()
        st.metric("Total Expenses", format_currency(expense_total))
    with summary_cols[2]:
        income_total = filtered[filtered["type"] == "income"]["amount"].sum()
        st.metric("Total Income", format_currency(income_total))
    with summary_cols[3]:
        transfer_total = filtered[filtered["type"] == "transfer"]["amount"].sum()
        st.metric("Total Transfers", format_currency(transfer_total))

    st.divider()

    # ── Display transactions with editable category ──
    if filtered.empty:
        st.info("No transactions match your filters.")
        return

    # Sort by date descending
    filtered = filtered.sort_values("date", ascending=False).reset_index(drop=True)

    # Keep track of original sheet row indices for editing
    # We need the original index from the full dataframe
    filtered_original_indices = filtered.index.tolist()

    # Build display dataframe
    display_df = filtered[["date", "description", "amount", "account", "category", "type"]].copy()
    display_df.columns = ["Date", "Description", "Amount", "Account", "Category", "Type"]

    all_cat_names = db.get_all_category_names(spreadsheet)
    # Include special categories and any existing categories not in the standard list
    extra_cats = ["Income", "Transfer"]
    existing_cats = filtered["category"].unique().tolist()
    full_cat_options = sorted(set(all_cat_names + extra_cats + [
        c for c in existing_cats if c and str(c).strip()
    ]))

    # Pagination
    page_size = 50
    total_pages = max(1, (len(display_df) + page_size - 1) // page_size)

    if "txn_page" not in st.session_state:
        st.session_state.txn_page = 1

    # Ensure page is within bounds
    if st.session_state.txn_page > total_pages:
        st.session_state.txn_page = total_pages

    current_page = st.session_state.txn_page
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, len(display_df))

    page_df = display_df.iloc[start_idx:end_idx].reset_index(drop=True)

    # Editable table
    edited_df = st.data_editor(
        page_df,
        column_config={
            "Date": st.column_config.TextColumn("Date", disabled=True, width="small"),
            "Description": st.column_config.TextColumn(
                "Description", disabled=True, width="large",
            ),
            "Amount": st.column_config.NumberColumn(
                "Amount", format="$%.2f", disabled=True, width="small",
            ),
            "Account": st.column_config.TextColumn(
                "Account", disabled=True, width="small",
            ),
            "Category": st.column_config.SelectboxColumn(
                "Category", options=full_cat_options, required=False, width="medium",
            ),
            "Type": st.column_config.TextColumn("Type", disabled=True, width="small"),
        },
        hide_index=True,
        use_container_width=True,
        key=f"txn_editor_page_{current_page}",
    )

    # Detect category changes and save
    changes_made = False
    for i, row in edited_df.iterrows():
        old_cat = page_df.iloc[i]["Category"]
        new_cat = row["Category"]
        if str(new_cat) != str(old_cat):
            # Find the original row index in the full records list
            # The filtered df index maps to the original df index
            filtered_idx = start_idx + i
            original_record_idx = filtered.iloc[filtered_idx].name

            # Find this transaction in the sheet by matching all fields
            all_records = db.get_all_transactions(spreadsheet)
            target = filtered.iloc[filtered_idx]
            for sheet_idx, rec in enumerate(all_records):
                if (str(rec.get("date", "")) == str(target["date"]) and
                    str(rec.get("description", "")) == str(target["description"]) and
                    float(rec.get("amount", 0)) == float(target["amount"]) and
                    str(rec.get("account", "")) == str(target["account"])):
                    db.update_transaction_category(spreadsheet, sheet_idx, new_cat)

                    # Also update vendor map if it's an expense
                    if target.get("type") == "expense" and new_cat and str(new_cat).strip():
                        vendor = parsers.clean_vendor_name(str(target["description"]))
                        if vendor:
                            db.update_vendor_map(spreadsheet, vendor, new_cat)
                    changes_made = True
                    break

    if changes_made:
        st.success("Category updated! Click **Refresh Data** to see updated budget numbers.")
        st.session_state.needs_refresh = True

    # Pagination controls
    if total_pages > 1:
        st.divider()
        pag_cols = st.columns([1, 2, 1])
        with pag_cols[0]:
            if st.button("◀ Previous", disabled=current_page <= 1, use_container_width=True):
                st.session_state.txn_page -= 1
                st.rerun()
        with pag_cols[1]:
            st.markdown(
                f"<div style='text-align: center; padding-top: 8px;'>"
                f"Page {current_page} of {total_pages} "
                f"({len(display_df)} transactions)</div>",
                unsafe_allow_html=True,
            )
        with pag_cols[2]:
            if st.button("Next ▶", disabled=current_page >= total_pages, use_container_width=True):
                st.session_state.txn_page += 1
                st.rerun()


# ─── SETTINGS ─────────────────────────────────────────────────────────────

def render_settings():
    st.header("Settings")

    # ── Starting Balance ──
    st.subheader("Starting Balance")
    st.caption(
        "Enter the balance of your bank account as of the date you start using this app. "
        "This should be your balance BEFORE any transactions you upload. "
        "If you've already uploaded transactions, use your balance from before the "
        "earliest uploaded transaction to avoid double-counting income."
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

    # ── Data Management ──
    st.subheader("Data Management")

    with st.expander("⚠️ Clear All Transactions"):
        st.caption(
            "This will delete ALL uploaded transactions. Your budget allocations "
            "and categories will be kept. This cannot be undone."
        )
        confirm_text = st.text_input(
            "Type DELETE to confirm",
            key="confirm_delete_txns",
            placeholder="Type DELETE here...",
        )
        if st.button("Clear All Transactions", type="secondary"):
            if confirm_text == "DELETE":
                try:
                    ws = spreadsheet.worksheet(db.TAB_TRANSACTIONS)
                    # Get all rows except header
                    all_data = ws.get_all_values()
                    if len(all_data) > 1:
                        # Delete all data rows (keep header)
                        ws.delete_rows(2, len(all_data))
                    st.success("All transactions cleared.")
                    st.session_state.needs_refresh = True
                    load_data()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error clearing transactions: {str(e)}")
            else:
                st.error("Please type DELETE to confirm.")

    with st.expander("⚠️ Clear Vendor Map"):
        st.caption(
            "This will reset the auto-suggest memory. The app will no longer "
            "remember which vendors go with which categories."
        )
        if st.button("Clear Vendor Map", type="secondary"):
            try:
                ws = spreadsheet.worksheet(db.TAB_VENDOR_MAP)
                all_data = ws.get_all_values()
                if len(all_data) > 1:
                    ws.delete_rows(2, len(all_data))
                st.success("Vendor map cleared.")
            except Exception as e:
                st.error(f"Error clearing vendor map: {str(e)}")

    with st.expander("⚠️ Clear Budget Allocations"):
        st.caption(
            "This will remove all monthly budget allocations across all months. "
            "Your categories and transactions will be kept."
        )
        confirm_budget = st.text_input(
            "Type DELETE to confirm",
            key="confirm_delete_budget",
            placeholder="Type DELETE here...",
        )
        if st.button("Clear All Budget Allocations", type="secondary"):
            if confirm_budget == "DELETE":
                try:
                    ws = spreadsheet.worksheet(db.TAB_BUDGET)
                    all_data = ws.get_all_values()
                    if len(all_data) > 1:
                        ws.delete_rows(2, len(all_data))
                    st.success("All budget allocations cleared.")
                    st.session_state.needs_refresh = True
                    load_data()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error clearing budgets: {str(e)}")
            else:
                st.error("Please type DELETE to confirm.")

    st.divider()

    # ── Category Management ──
    st.subheader("Category Management")
    categories = st.session_state.get("categories", {})

    if categories:
        for group_name, cat_list in categories.items():
            with st.expander(f"**{group_name}** ({len(cat_list)} categories)"):
                col_rg1, col_rg2 = st.columns([3, 1])
                with col_rg1:
                    new_group_name = st.text_input(
                        "Rename group", value=group_name,
                        key=f"rename_group_{group_name}",
                    )
                with col_rg2:
                    st.write("")
                    st.write("")
                    if new_group_name != group_name and st.button(
                        "Rename", key=f"btn_rename_group_{group_name}"
                    ):
                        db.rename_group(spreadsheet, group_name, new_group_name)
                        st.success(f"Renamed '{group_name}' to '{new_group_name}'")
                        st.session_state.needs_refresh = True
                        load_data()
                        st.rerun()

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

                st.write("")
                col_add1, col_add2 = st.columns([3, 1])
                with col_add1:
                    new_cat = st.text_input(
                        "New category name", key=f"add_cat_{group_name}",
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

                st.write("")
                if st.button(
                    f"🗑️ Delete entire '{group_name}' group",
                    key=f"del_group_{group_name}", type="secondary",
                ):
                    db.delete_group(spreadsheet, group_name)
                    st.warning(f"Deleted group '{group_name}' and all its categories.")
                    st.session_state.needs_refresh = True
                    load_data()
                    st.rerun()
    else:
        st.warning("No categories found. Add a group below to get started.")

    # Add New Group
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
            placeholder="e.g., Bus Pass", key="new_group_first_cat",
        )
    with col_ng3:
        st.write("")
        st.write("")
        if st.button("Create Group") and new_group and first_cat:
            if new_group in categories:
                st.error(f"Group '{new_group}' already exists.")
            else:
                group_order = db.add_group(spreadsheet, new_group)
                ws = spreadsheet.worksheet(db.TAB_CATEGORIES)
                ws.append_row(
                    [new_group, first_cat, group_order, 0],
                    value_input_option="USER_ENTERED",
                )
                st.success(f"Created group '{new_group}' with category '{first_cat}'")
                st.session_state.needs_refresh = True
                load_data()
                st.rerun()

    st.divider()

    # ── Vendor Map Viewer ──
    st.subheader("Vendor Map (Auto-Suggest Memory)")
    st.caption(
        "This is what the app has learned about your vendors. "
        "When you upload a CSV, it uses this to auto-suggest categories."
    )
    try:
        vendor_map = db.get_vendor_map(spreadsheet)
        if vendor_map:
            vm_df = pd.DataFrame([
                {"Vendor": k, "Category": v} for k, v in sorted(vendor_map.items())
            ])
            st.dataframe(vm_df, hide_index=True, use_container_width=True)
        else:
            st.caption("No vendor mappings yet. They'll build up as you categorize transactions.")
    except Exception:
        st.caption("No vendor mappings yet.")


# ─── RENDER SELECTED PAGE ────────────────────────────────────────────────

if page == "Budget":
    render_budget_view()
elif page == "Upload & Categorize":
    render_upload()
elif page == "Transactions":
    render_transactions()
elif page == "Settings":
    render_settings()
