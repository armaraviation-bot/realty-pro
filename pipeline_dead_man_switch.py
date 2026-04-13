#!/usr/bin/env python3
"""
Pipeline Dead Man's Switch v1
Detects when the SRX scraper silently returns 0 leads (no error, just empty).
Fires alert + writes ~/.pipeline_dead sentinel → triggers auto-recovery in downstream jobs.
Run: python3 skills/realty-pro/pipeline_dead_man_switch.py
"""
import json, os, sys
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE = os.path.expanduser("~/.openclaw/workspace/")
LEADS_FILE = os.path.join(WORKSPACE, "property_leads.json")
SENTINEL = os.path.expanduser("~/.pipeline_dead")
STATE_FILE = os.path.join(WORKSPACE, "pipeline_dms_state.json")
ALERT_FILE = os.path.join(WORKSPACE, "pipeline_dms_alert.json")

TELEGRAM_CHAT_ID = "623788698"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"[{ts}] {msg}")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"last_check": None, "last_lead_count": None, "consecutive_empty": 0}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def check_leads():
    """Check if property_leads.json has recent, non-empty leads from today."""
    today = datetime.now().strftime("%Y-%m-%d")
    
    if not os.path.exists(LEADS_FILE):
        return {"status": "MISSING", "count": 0, "message": "property_leads.json not found"}
    
    try:
        with open(LEADS_FILE) as f:
            leads = json.load(f)
    except Exception as e:
        return {"status": "CORRUPT", "count": 0, "message": f"Could not parse leads file: {e}"}
    
    if not isinstance(leads, list):
        return {"status": "CORRUPT", "count": 0, "message": "Leads file is not a list"}
    
    count = len(leads)
    
    # Check if leads are from today
    today_leads = [l for l in leads if l.get("timestamp", "").startswith(today)]
    today_count = len(today_leads)
    
    # Check file modification time
    mtime = os.path.getmtime(LEADS_FILE)
    file_age = datetime.now() - datetime.fromtimestamp(mtime)
    
    if today_count > 0:
        return {
            "status": "HEALTHY",
            "count": today_count,
            "message": f"{today_count} leads from today ({today})"
        }
    elif count > 0:
        # Leads exist but not from today
        latest = max(l.get("timestamp", "") for l in leads)
        return {
            "status": "STALE",
            "count": count,
            "message": f"Last leads were from {latest}, not today ({today})"
        }
    else:
        return {
            "status": "EMPTY",
            "count": 0,
            "message": "No leads in file"
        }

def write_sentinel(reason):
    """Write the pipeline_dead sentinel with context."""
    with open(SENTINEL, "w") as f:
        json.dump({
            "triggered_at": datetime.now().isoformat(),
            "reason": reason
        }, f, indent=2)
    log(f"⚠️  Sentinel written: {SENTINEL}")

def clear_sentinel():
    """Remove the sentinel if pipeline is healthy."""
    if os.path.exists(SENTINEL):
        os.remove(SENTINEL)
        log("✅ Sentinel cleared — pipeline healthy")

def send_telegram_alert(message: str):
    """Send alert via system event (main session will relay)."""
    # Write alert to file for main session to pick up
    with open(ALERT_FILE, "w") as f:
        json.dump({
            "message": message,
            "triggered_at": datetime.now().isoformat(),
            "chat_id": TELEGRAM_CHAT_ID
        }, f, indent=2)
    log(f"📨 Alert written to {ALERT_FILE}")

def run():
    log("🔎 Pipeline Dead Man's Switch starting...")
    state = load_state()
    check = check_leads()
    
    log(f"   Status: {check['status']} — {check['message']}")
    
    if check["status"] == "HEALTHY":
        # Pipeline OK
        clear_sentinel()
        state["consecutive_empty"] = 0
        state["last_check"] = datetime.now().isoformat()
        state["last_lead_count"] = check["count"]
        save_state(state)
        log(f"✅ Pipeline HEALTHY — {check['count']} leads. Sentinel cleared.")
        # Output plain HEALTHY for agentTurn announce suppression
        print("HEALTHY")
        return
    
    # Pipeline is EMPTY, STALE, or MISSING/CORRUPT
    consecutive = state.get("consecutive_empty", 0) + 1
    state["consecutive_empty"] = consecutive
    state["last_check"] = datetime.now().isoformat()
    state["last_lead_count"] = check["count"]
    save_state(state)
    
    # Only fire on first detection or every 3 consecutive failures
    # (avoid spamming if scraper keeps failing)
    should_alert = consecutive == 1 or (consecutive % 3 == 0)
    
    if should_alert:
        write_sentinel(check["message"])
        log(f"🚨 ALERT FIRED — consecutive={consecutive}")
        
        # Full Telegram-ready alert goes to stdout (agentTurn announce will deliver it)
        alert_lines = [
            "🔴 PIPELINE EMPTY — Dead Man's Switch Fired",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"Status: {check['status']}",
            f"Reason: {check['message']}",
            f"Consecutive failures: {consecutive}",
            f"",
            f"⚙️  AUTO-RECOVERY ACTIVE",
            f"→ Morning Pulse will fetch from 99.co",
            f"→ Brave Search (Active Scout) unaffected",
            f"→ Shortlist & Sheets will use fallback",
            f"",
            f"_Pipeline will self-heal on next run_",
            f"🦞 Dead Man's Switch v1",
        ]
        print("\n".join(alert_lines))
    else:
        log(f"⚠️  Pipeline dead but alert suppressed (consecutive={consecutive}, fires every 3rd)")
        print(f"DEAD:SUPPRESSED:{check['status']}")

if __name__ == "__main__":
    run()
