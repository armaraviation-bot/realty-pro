#!/usr/bin/env python3
"""
Mogul Scout Runner — Dual-Platform Edition
==========================================
Smart caching + dual-platform split (SRX + 99.co)

Cache logic:
- Valid cache: <24h old → skip scrape, use cached leads
- Stale cache: >24h → run dual_hunter
- SRX cooldown: automatically detected, 99.co runs exclusively
"""
import json
import os
import sys
import asyncio
import subprocess
from datetime import datetime, timedelta

workspace = os.path.expanduser("~/.openclaw/workspace/")
leads_path = os.path.join(workspace, "property_leads.json")
cache_meta_path = os.path.join(workspace, "property_cache_meta.json")
dual_hunter_path = os.path.join(os.path.dirname(__file__), "../scraper/dual_hunter.py")

CACHE_HOURS = 24


def check_cache():
    """Check if we have valid cached data."""
    if not os.path.exists(leads_path):
        return False, "No leads file found"

    if not os.path.exists(cache_meta_path):
        mtime = os.path.getmtime(leads_path)
        age_hours = (datetime.now().timestamp() - mtime) / 3600
        if age_hours < CACHE_HOURS:
            return True, f"Using existing leads ({age_hours:.1f}h old)"
        return False, f"Leads file is {age_hours:.1f}h old"

    with open(cache_meta_path, 'r') as f:
        meta = json.load(f)

    last_scrape = datetime.fromisoformat(meta.get('last_scrape', '2020-01-01'))
    age = datetime.now() - last_scrape

    if age < timedelta(hours=CACHE_HOURS):
        return True, f"Cache valid ({age.total_seconds()/3600:.1f}h old)"

    return False, f"Cache stale ({age.total_seconds()/3600:.1f}h old)"


def update_cache_meta(new_leads_count=0):
    """Update cache metadata."""
    meta = {
        'last_scrape': datetime.now().isoformat(),
        'leads_count': 0,
        'source': 'dual_hunter'
    }

    if os.path.exists(leads_path):
        with open(leads_path, 'r') as f:
            leads = json.load(f)
            meta['leads_count'] = len(leads)

    with open(cache_meta_path, 'w') as f:
        json.dump(meta, f, indent=2)


def show_stats():
    """Show quick lead stats."""
    if not os.path.exists(leads_path):
        return

    with open(leads_path, 'r') as f:
        leads = json.load(f)

    by_source = {}
    by_eip = {"OPEN": [], "CLOSED": [], "UNKNOWN": []}
    by_priority = {"high": [], "medium": []}

    for lead in leads:
        src = lead.get("source", "UNKNOWN")
        by_source[src] = by_source.get(src, 0) + 1
        eip = lead.get("eip_status", "UNKNOWN")
        by_eip[eip] = by_eip.get(eip, []) + [lead]
        pri = lead.get("priority", "medium")
        by_priority[pri] = by_priority.get(pri, []) + [lead]

    print(f"\n📊 Buffer Stats ({len(leads)} total leads):")
    print(f"   By source: {by_source}")
    print(f"   EIP OPEN: {len(by_eip['OPEN'])} | CLOSED: {len(by_eip['CLOSED'])}")
    print(f"   High priority: {len(by_priority['high'])}")


def main():
    print("🕵️ Mogul Scout Runner — Dual-Platform Edition")
    print("=" * 50)

    # Check cache
    cache_valid, message = check_cache()
    print(f"📋 Cache check: {message}")

    if cache_valid:
        print("✅ Using cached data — skipping scrape!")
        show_stats()
        return 0

    print("⏳ Cache stale or missing — running Dual Hunter...")
    print()

    # Run dual hunter via subprocess (isolated browser processes)
    venv_python = "/home/admin/venv/bin/python3"

    result = subprocess.run(
        [venv_python, dual_hunter_path],
        cwd=workspace,
        env={**os.environ},
        capture_output=True,
        text=True,
        timeout=300
    )

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr[:500])

    if result.returncode == 0:
        print("\n✅ Dual Hunter completed successfully!")
        update_cache_meta()
        show_stats()
        return 0
    else:
        print(f"\n❌ Dual Hunter failed (exit {result.returncode})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
