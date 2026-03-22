# 💰 Budget App

A personal budgeting app inspired by YNAB, built with Streamlit and backed by Google Sheets.

## Setup

### 1. Clone this repo

```bash
git clone https://github.com/YOUR_USERNAME/budget-app.git
cd budget-app
```

### 2. Configure secrets

Create the secrets file for local development:

```bash
mkdir -p .streamlit
cp secrets_template.toml .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` and fill in:

- **app_password**: Choose a password for the app
- **spreadsheet_id**: The ID from your Google Sheet URL (the long string between `/d/` and `/edit`)
- **gcp_service_account**: Copy the entire contents of your downloaded JSON credentials file, but reformat it as TOML key-value pairs under the `[gcp_service_account]` section

#### Converting the JSON credentials to TOML

Your downloaded JSON file looks like:
```json
{
  "type": "service_account",
  "project_id": "budget-app-123456",
  "private_key_id": "abc123...",
  ...
}
```

In your `secrets.toml`, it becomes:
```toml
[gcp_service_account]
type = "service_account"
project_id = "budget-app-123456"
private_key_id = "abc123..."
...
```

Copy each key-value pair from the JSON into the TOML format. Make sure the `private_key` value keeps its `\n` characters as literal text (don't convert them to actual newlines).

### 3. Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

### 4. Deploy to Streamlit Cloud

1. Push your code to GitHub (secrets are in `.gitignore` and won't be uploaded)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set the main file path to `app.py`
5. Go to **Settings** > **Secrets** and paste the full contents of your `.streamlit/secrets.toml`
6. Click **Deploy**

## Project Structure

```
budget-app/
├── app.py                  # Main Streamlit app (UI and navigation)
├── db.py                   # Google Sheets database layer
├── requirements.txt        # Python dependencies
├── .gitignore              # Keeps secrets out of git
├── secrets_template.toml   # Template showing required secrets
└── README.md               # This file
```

## Phases

- **Phase 1** ✅ — Budget view, category management, manual allocation, rolling balances
- **Phase 2** — CSV upload (Columbia Bank, Capitol One, Chase), transaction categorization with auto-suggest
- **Phase 3** — Transaction list with search/filter/edit, settings refinements
