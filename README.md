# 🏘️ Realty Pro — Setup Guide

## Prerequisites

1. **OpenClaw** installed and running
2. **Python 3.12+** with venv
3. **Google Account** (for Sheets)

---

## Step 1: Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required packages
pip install playwright google-auth google-auth-oauthlib gspread
playwright install chromium
```

---

## Step 2: Google Sheets Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project: `realty-pro`
3. Enable **Google Sheets API** and **Google Drive API**
4. Go to **IAM & Admin** → **Service Accounts**
5. Create service account: `realty-pro@realty-pro.iam.gserviceaccount.com`
6. Click **Keys** → **Add Key** → **JSON** → Download file
7. Rename downloaded file to `google_credentials.json`
8. Place in `sheets/` folder

9. Create new Google Sheet
10. **Share** → Add email: `realty-pro@realty-pro.iam.gserviceaccount.com` → Editor

---

## Step 3: Configure Scraper

Edit `scraper/hunter_settings.json`:

```json
{
  "url": "https://www.srx.com.sg/search/sale/hdb/hougang",
  "max_price": 1000000,
  "keywords": ["executive", "maisonette"]
}
```

**URL Options:**
- HDB: `https://www.srx.com.sg/search/sale/hdb/[town]`
- Condo: `https://www.srx.com.sg/search/sale/condo/[district]`

---

## Step 4: Run Manually

```bash
source venv/bin/activate

# Scrape leads from SRX
cd scraper
python3 property_hunter.py

# Push to Google Sheets
cd ../sheets
python3 push_to_sheet.py
```

---

## Step 5: Schedule Daily Run

Add to OpenClaw cron (via dashboard or CLI):

- **Time:** 07:00 SGT daily
- **Task:** Run pipeline and send Telegram summary

---

## Troubleshooting

### "Just a moment..." blocker
- SRX has Cloudflare protection
- Use the provided Playwright stealth settings
- If consistently blocked, try different time of day

### Sheet not updating
- Verify Service Account has Editor access
- Check `google_credentials.json` is valid JSON

### No leads found
- Check URL is valid SRX search
- Verify `max_price` and `keywords` filters

---

## Files

```
realty-pro/
├── SKILL.md                      # Skill definition
├── README.md                     # This file
├── scraper/
│   ├── property_hunter.py       # SRX scraper
│   └── hunter_settings.json    # Configuration
└── sheets/
    ├── push_to_sheet.py        # Sheet pusher
    └── google_credentials.json # Your service account
```

---

**Author:** Built with 🦞 by Gandalf + OpenClaw
