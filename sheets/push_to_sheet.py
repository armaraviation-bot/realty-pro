#!/usr/bin/env python3
"""Mogul Scout - Push leads to Google Sheets"""
import json
import os
from datetime import datetime
from google.oauth2 import service_account
from google.auth.transport.requests import Request
import gspread

# Paths
workspace = os.path.expanduser("~/.openclaw/workspace/")
creds_path = os.path.join(workspace, "google_credentials.json")
leads_path = os.path.join(workspace, "property_leads.json")
sheet_id = "18LCrWMkbAnY1R8BDn-gSU3Y8NZJEkZleRlLQ7b4_8TQ"

# Load leads
with open(leads_path, "r") as f:
    leads = json.load(f)

# Authenticate
creds = service_account.Credentials.from_service_account_file(
    creds_path,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
client = gspread.authorize(creds)

# Open sheet
sheet = client.open_by_key(sheet_id)
ws = sheet.sheet1

# Build header + data
headers = ["Rank", "Address", "Price", "PSF", "Days Old", "Score", "URL", "Scraped", "EIP Status", "Notes"]
today = datetime.now().strftime("%Y-%m-%d")

# Parse leads (simplified - in production, parse more fields)
data = []
for i, lead in enumerate(leads):
    # Extract info from summary
    summary = lead.get("summary", "")
    price = lead.get("price", "$0")
    link = lead.get("link", "")
    
    # Simple scoring logic
    psf_val = int(price.replace("$", "").replace(",", ""))
    if psf_val < 600:
        score = "🔥 9/10"
    elif psf_val < 650:
        score = "8/10"
    elif psf_val < 700:
        score = "7/10"
    else:
        score = "6/10"
    
    # Extract address from summary
    address = summary.split("HDB")[0].strip() if "HDB" in summary else summary[:50]
    days_old = "1d"  # Default
    
    data.append([i+1, address, price, price, days_old, score, link, today, "⏳ Pending", ""])

# Clear sheet and write
ws.clear()
ws.update(values=[headers], range_name="A1")
ws.update(values=data, range_name="A2")

print(f"✅ Pushed {len(leads)} leads to Google Sheet")
