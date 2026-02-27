---
name: realty-pro
description: "Full B2B Real Estate Intelligence Skill — Automated lead scraping, distress analysis, and Google Sheets integration for Singapore properties."
user-invocable: true
metadata:
  openclaw:
    emoji: "🏘️"
    category: "realty"
    tags: ["real estate", "property", "leads", "singapore", "hdb", "condo", "automation"]
---

# 🏘️ Realty Pro — B2B Real Estate Intelligence

Automated property lead generation + distress analysis for Singapore real estate agents.

## What It Does

| Module | Function |
|--------|----------|
| 🔍 **Lead Scraper** | SRX/HDB listings by district/price/keywords |
| 📊 **Distress Analyzer** | Scores leads by: price drop, days on market, EIP traps |
| 📋 **Sheet Pusher** | Auto-populates Google Sheets with scored leads |
| ⏰ **Scheduler** | Daily 07:00 automated run + manual trigger |
| 🔔 **Notifier** | Telegram alerts with top picks |

## Quick Start

### 1. Setup Google Sheets

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project → Enable **Sheets API**
3. Create **Service Account** → Download JSON key
4. Create a Google Sheet
5. Share Sheet with: `your-service-account@project.iam.gserviceaccount.com` (Editor)
6. Save JSON as `google_credentials.json`

### 2. Configure

Edit `scraper/hunter_settings.json`:
```json
{
  "url": "https://www.srx.com.sg/search/sale/hdb/hougang",
  "max_price": 1000000,
  "keywords": ["executive", "maisonette"]
}
```

### 3. Run the Pipeline

```bash
# Scrape leads
python3 property_hunter.py

# Push to Sheet
python3 push_to_sheet.py
```

### 4. Schedule (Optional)

Add to OpenClaw cron for daily 07:00 runs.

## File Structure

```
realty-pro/
├── SKILL.md                  # This file
├── scraper/
│   ├── property_hunter.py    # SRX scraper (Playwright)
│   └── hunter_settings.json # Configuration
├── sheets/
│   ├── push_to_sheet.py     # Google Sheets API
│   └── google_credentials.json # Your service account
└── README.md               # Setup guide
```

## Distress Scoring Logic

| Factor | Weight | Criteria |
|--------|--------|----------|
| Price PSF | 30% | Below district avg = higher score |
| Days on Market | 25% | 30+ days = motivated seller |
| EIP Status | 20% | Quota near-full = liquidity risk |
| Price History | 15% | Multiple cuts = motivated |
| Property Type | 10% | Executive/ Maisonette = premium |

## Constraints

- Respect rate limits — don't hammer SRX
- Validate EIP manually (no live API)
- Store credentials locally — never commit to git
- For Singapore properties only

---

*Built with 🦞 by Gandalf + OpenClaw*
