#!/usr/bin/env python3
"""
DUAL HUNTER — Dual-Platform Split Protocol
==========================================
Orchestrates SRX (60%) + 99.co (40%) with automatic failover.

Cooldown Logic:
- If SRX yields <3 listings → trigger 24h cooldown lock
- During cooldown: SRX skipped, 99.co runs exclusively
- Cooldown auto-expires after 24h

Usage:
  python3 dual_hunter.py              # Normal dual run
  python3 dual_hunter.py --srx-only   # Debug: SRX only
  python3 dual_hunter.py --99co-only # Debug: 99.co only
  python3 dual_hunter.py --clear-cooldown  # Manual cooldown clear
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta

WORKSPACE = os.path.expanduser("~/.openclaw/workspace/")
COOLDOWN_LOCK = os.path.join(WORKSPACE, "srx_cooldown.lock")
LEADS_PATH = os.path.join(WORKSPACE, "property_leads.json")

# Thresholds
SRX_COOLDOWN_HOURS = 24
SRX_MIN_LISTINGS = 3  # Below this → trigger cooldown


def is_srx_in_cooldown():
    """Check if SRX is in cooldown period."""
    if not os.path.exists(COOLDOWN_LOCK):
        return False

    with open(COOLDOWN_LOCK, "r") as f:
        data = json.load(f)

    cooldown_until = datetime.fromisoformat(data["cooldown_until"])
    now = datetime.now()

    if now < cooldown_until:
        remaining = (cooldown_until - now).total_seconds() / 3600
        print(f"   ⏳ SRX cooldown active — {remaining:.1f}h remaining")
        return True
    else:
        # Expired — clean up
        os.remove(COOLDOWN_LOCK)
        print(f"   🔄 SRX cooldown expired — resuming normal operations")
        return False


def trigger_srx_cooldown(reason=""):
    """Lock SRX for 24h after a poor yield."""
    cooldown_until = (datetime.now() + timedelta(hours=SRX_COOLDOWN_HOURS)).isoformat()
    with open(COOLDOWN_LOCK, "w") as f:
        json.dump({
            "triggered_at": datetime.now().isoformat(),
            "cooldown_until": cooldown_until,
            "reason": reason
        }, f, indent=2)
    print(f"   🔒 SRX cooldown TRIGGERED — locked until {cooldown_until}")
    print(f"   Reason: {reason}")


async def run_srx():
    """Run SRX hunter. Returns (success, listing_count, leads)."""
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from srx_direct_hunter import run as srx_run
        leads = await srx_run()
        return True, len(leads), leads
    except Exception as e:
        print(f"   ❌ SRX failed: {e}")
        return False, 0, []


async def run_99co():
    """Run 99.co hunter. Returns (success, listing_count, leads)."""
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from co99_hunter import run as co99_run
        leads = await co99_run()
        return True, len(leads), leads
    except Exception as e:
        print(f"   ❌ 99.co failed: {e}")
        return False, 0, []


def save_leads(all_leads):
    """Merge and deduplicate leads."""
    existing = []
    if os.path.exists(LEADS_PATH):
        with open(LEADS_PATH, "r") as f:
            try:
                existing = json.load(f)
            except:
                existing = []

    existing_urls = {l["link"] for l in existing if l.get("link")}
    new_leads = [l for l in all_leads if l.get("link", "") not in existing_urls]

    combined = existing + new_leads
    with open(LEADS_PATH, "w") as f:
        json.dump(combined, f, indent=2)

    return len(new_leads), len(combined)


async def run(mode="auto"):
    """
    Modes:
      auto    — Dual platform, respects cooldown
      srx     — SRX only
      99co    — 99.co only
      force   — Both platforms regardless of cooldown
    """
    print("=" * 55)
    print("🧙‍♂️ DUAL HUNTER — Dual-Platform Split Protocol v1.0")
    print("=" * 55)

    srx_in_cooldown = is_srx_in_cooldown()
    all_leads = []

    # ── AUTO / DUAL ──────────────────────────────────────────
    if mode in ("auto", "dual"):

        if srx_in_cooldown:
            # SRX locked — 99.co exclusively
            print("\n[PHASE 1] SRX: SKIPPED (in cooldown)")
            print("[PHASE 2] 99.co: ACTIVE")
            _, count_99, leads_99 = await run_99co()
            all_leads.extend(leads_99)
            print(f"\n📊 Session result: {count_99} from 99.co (SRX locked)")

        else:
            # Both active — SRX 60%, 99.co 40%
            print("\n[PHASE 1] SRX: ACTIVE (60% capacity)")
            success_srx, count_srx, leads_srx = await run_srx()
            all_leads.extend(leads_srx)

            print("\n[PHASE 2] 99.co: ACTIVE (40% capacity)")
            success_99, count_99, leads_99 = await run_99co()
            all_leads.extend(leads_99)

            print(f"\n📊 Session result: {count_srx} from SRX + {count_99} from 99.co")

            # Evaluate — trigger cooldown if SRX performed poorly
            if success_srx and count_srx < SRX_MIN_LISTINGS:
                trigger_srx_cooldown(f"Low yield: {count_srx} listings (threshold: {SRX_MIN_LISTINGS})")

    # ── SRX ONLY ─────────────────────────────────────────────
    elif mode == "srx":
        print("\n[MODE] SRX ONLY (debug)")
        success, count, leads = await run_srx()
        all_leads.extend(leads)
        print(f"\n📊 SRX result: {count} listings")

        if success and count < SRX_MIN_LISTINGS:
            trigger_srx_cooldown(f"Low yield (manual trigger): {count} listings")

    # ── 99.CO ONLY ───────────────────────────────────────────
    elif mode == "99co":
        print("\n[MODE] 99.co ONLY (debug)")
        success, count, leads = await run_99co()
        all_leads.extend(leads)
        print(f"\n📊 99.co result: {count} listings")

    # ── SAVE ─────────────────────────────────────────────────
    if all_leads:
        new_count, total = save_leads(all_leads)
        print(f"\n💾 Saved {new_count} new leads → {total} total in buffer")
    else:
        print("\n⚠️ No leads captured this session")

    print("\n✅ Dual Hunter session complete")
    return all_leads


if __name__ == "__main__":
    mode = "auto"
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "--srx-only":
            mode = "srx"
        elif arg == "--99co-only":
            mode = "99co"
        elif arg == "--force":
            mode = "force"
        elif arg == "--clear-cooldown":
            if os.path.exists(COOLDOWN_LOCK):
                os.remove(COOLDOWN_LOCK)
                print("🔓 SRX cooldown cleared manually")
            else:
                print("No cooldown lock file found")
            sys.exit(0)

    asyncio.run(run(mode))
