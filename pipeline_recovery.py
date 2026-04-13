#!/usr/bin/env python3
"""
Pipeline Auto-Recovery Module
Imported by downstream realty scripts to check for pipeline_dead sentinel.
When sentinel exists, scripts switch to fallback data sources (99.co, PropertyGuru).
Usage:
  from pipeline_recovery import is_pipeline_dead, get_fallback_leads, log_recovery
"""
import json, os, sys, asyncio, re
from datetime import datetime
from pathlib import Path

WORKSPACE = os.path.expanduser("~/.openclaw/workspace/")
SENTINEL = os.path.expanduser("~/.pipeline_dead")
FALLBACK_LEADS_FILE = os.path.join(WORKSPACE, "fallback_leads.json")

def is_pipeline_dead():
    """Returns True if pipeline_dead sentinel exists."""
    return os.path.exists(SENTINEL)

def get_sentinel_reason():
    """Returns the reason stored in the sentinel, or 'unknown'."""
    if not is_pipeline_dead():
        return None
    try:
        with open(SENTINEL) as f:
            data = json.load(f)
        return data.get("reason", "unknown")
    except:
        return "unknown"

def log_recovery(script_name: str, method: str, lead_count: int):
    """Log that recovery mode was used."""
    reason = get_sentinel_reason()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"[{ts}] 🔄 [{script_name}] AUTO-RECOVERY: used {method} — {lead_count} leads (pipeline_dead reason: {reason})")

async def fetch_fallback_leads():
    """
    Fetch leads from fallback sources when SRX pipeline is dead.
    Uses 99.co public search API as primary fallback.
    Returns list of lead dicts compatible with property_leads.json format.
    """
    try:
        import requests
        
        # Try 99.co API - their public search endpoint
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        
        # Search for condos in Singapore, price < 1.5M
        url = "https://www.99.co/api/v2/listing/search"
        params = {
            "layout": "1",
            "limit": 30,
            "property_type": "condo",
            "price_max": 1500000,
            "price_min": 0,
            "rental_type": "sale",
        }
        
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                listings = data.get("data", {}).get("listings", [])
                
                leads = []
                for item in listings:
                    title = item.get("title", item.get("address", "Unknown"))
                    price_str = item.get("price", item.get("price_formatted", ""))
                    link = item.get("url", "")
                    if link and not link.startswith("http"):
                        link = f"https://www.99.co{link}"
                    
                    leads.append({
                        "summary": f"{title} | Price: {price_str}",
                        "price": price_str,
                        "psf": item.get("psf", "N/A"),
                        "link": link,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "full_address": title,
                        "address": title,
                        "_source": "99.co_fallback",
                        "_recovery": True
                    })
                
                with open(FALLBACK_LEADS_FILE, "w") as f:
                    json.dump(leads, f, indent=2)
                
                return leads
        except Exception as e:
            print(f"   99.co fallback failed: {e}")
        
        # Fallback 2: Search via Brave/Serper for property listings
        # (handled by the calling script using brave_search)
        return []
        
    except ImportError:
        print("   requests not available for fallback")
        return []

def get_fallback_leads():
    """Synchronous read of fallback leads file if it exists."""
    if os.path.exists(FALLBACK_LEADS_FILE):
        try:
            with open(FALLBACK_LEADS_FILE) as f:
                return json.load(f)
        except:
            pass
    return []

# ─────────────────────────────────────────────
# Unit test when run directly
# ─────────────────────────────────────────────
if __name__ == "__main__":
    dead = is_pipeline_dead()
    reason = get_sentinel_reason()
    fallback = get_fallback_leads()
    
    print(f"Pipeline Dead: {dead}")
    print(f"Sentinel Reason: {reason}")
    print(f"Fallback Leads Available: {len(fallback)}")
