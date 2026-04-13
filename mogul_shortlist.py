#!/usr/bin/env python3
"""
MOGUL SHORTLIST GENERATOR v2.0
==============================
Reads enriched leads from property_leads.json,
applies EIP zone analysis + distress scoring,
outputs MOGUL_SHORTLIST.md — the B2B daily deliverable.

Run after: srx_direct_hunter.py (or any scraper that produces property_leads.json)
"""
import json
import os
from datetime import datetime

WORKSPACE = os.path.expanduser("~/.openclaw/workspace/")
LEADS_PATH = os.path.join(WORKSPACE, "property_leads.json")
SHORTLIST_PATH = os.path.join(WORKSPACE, "MOGUL_SHORTLIST.md")
TELEGRAM_BRIEF_PATH = os.path.join(WORKSPACE, "memory/mogul_brief_latest.md")

# EIP Zones
EIP_ZONES = {
    "D01": {"name": "Raffles Place", "eip": "OPEN", "ethnicity": "Chinese"},
    "D02": {"name": "Tanjong Pagar", "eip": "OPEN", "ethnicity": "Chinese"},
    "D03": {"name": "Queenstown", "eip": "OPEN", "ethnicity": "Mixed"},
    "D04": {"name": "Telok Blangah", "eip": "CLOSED", "ethnicity": "Malay"},
    "D05": {"name": "Clementi", "eip": "OPEN", "ethnicity": "Chinese"},
    "D06": {"name": "Bukit Merah", "eip": "CLOSED", "ethnicity": "Chinese"},
    "D07": {"name": "Tanjong Pagar", "eip": "OPEN", "ethnicity": "Chinese"},
    "D08": {"name": "Outram", "eip": "OPEN", "ethnicity": "Chinese"},
    "D09": {"name": "River Valley", "eip": "OPEN", "ethnicity": "Chinese"},
    "D10": {"name": "Tanglin", "eip": "OPEN", "ethnicity": "Chinese"},
    "D11": {"name": "Newton", "eip": "OPEN", "ethnicity": "Chinese"},
    "D12": {"name": "Toa Payoh", "eip": "CLOSED", "ethnicity": "Chinese"},
    "D13": {"name": "Macpherson", "eip": "CLOSED", "ethnicity": "Chinese"},
    "D14": {"name": "Geylang", "eip": "CLOSED", "ethnicity": "Malay"},
    "D15": {"name": "Katong", "eip": "CLOSED", "ethnicity": "Chinese"},
    "D16": {"name": "Bedok", "eip": "CLOSED", "ethnicity": "Mixed"},
    "D17": {"name": "Changi", "eip": "OPEN", "ethnicity": "Mixed"},
    "D18": {"name": "Tampines", "eip": "OPEN", "ethnicity": "Chinese"},
    "D19": {"name": "Serangoon", "eip": "OPEN", "ethnicity": "Chinese"},
    "D20": {"name": "Ang Mo Kio", "eip": "OPEN", "ethnicity": "Chinese"},
    "D21": {"name": "Bishan", "eip": "OPEN", "ethnicity": "Chinese"},
    "D22": {"name": "Jurong", "eip": "OPEN", "ethnicity": "Chinese"},
    "D23": {"name": "Lim Chu Kang", "eip": "CLOSED", "ethnicity": "Chinese"},
    "D24": {"name": "West Coast", "eip": "OPEN", "ethnicity": "Chinese"},
    "D25": {"name": "Woodlands", "eip": "OPEN", "ethnicity": "Chinese"},
    "D26": {"name": "Mandai", "eip": "OPEN", "ethnicity": "Chinese"},
    "D27": {"name": "Seletar", "eip": "OPEN", "ethnicity": "Mixed"},
    "D28": {"name": "Sembawang", "eip": "OPEN", "ethnicity": "Chinese"},
}

# Max price filter (default $1.5M for mogul picks)
MAX_PRICE = 1500000


def score_lead(lead):
    """
    Distress/opportunity score out of 100.
    Factors: price, PSF, EIP status, property type.
    """
    score = 50  # base

    # Price factor (under $1M = +15, under $1.2M = +10)
    pv = lead.get("price_val", 0)
    if pv > 0:
        if pv < 800000:
            score += 20
        elif pv < 1000000:
            score += 15
        elif pv < 1200000:
            score += 10
        elif pv < 1500000:
            score += 5

    # PSF factor (lower = better value, +15 for sub-$700psf)
    psf = lead.get("psf_val", 0)
    if psf > 0:
        if psf < 600:
            score += 20
        elif psf < 700:
            score += 15
        elif psf < 800:
            score += 10
        elif psf < 900:
            score += 5

    # EIP Open = +10 (liquidity + ethnic quota flexibility)
    if lead.get("eip_status") == "OPEN":
        score += 10

    # Executive/Maisonette/Penthouse = +5 (premium, motivated sellers)
    addr = lead.get("address", "").lower()
    if any(t in addr for t in ["executive", "maisonette", "penthouse", "duplex"]):
        score += 5

    # Clamp to 100
    return min(score, 100)


def detect_district(address, title=""):
    """Detect district from text."""
    text = (address + " " + title)
    match = __import__("re").search(r'\(D(\d+)\)', text)
    if match:
        d = f"D{match.group(1)}"
        zone = EIP_ZONES.get(d, {"name": "Unknown", "eip": "UNKNOWN", "ethnicity": "Unknown"})
        return d, zone["name"], zone["eip"], zone["ethnicity"]

    # Area-name fallback
    area_map = {
        "hougang": "D19", "serangoon": "D19", "sengkang": "D19",
        "tampines": "D18", "pasir ris": "D18",
        "bedok": "D16", "east coast": "D15",
        "geylang": "D14", "katong": "D15", "marine parade": "D15",
        "changi": "D17", "jurong": "D22", "bukit Merah": "D06",
        "toapayoh": "D12", "macpherson": "D13", "bishan": "D21",
        "ang mo kio": "D20", "woodlands": "D25", "yishun": "D25",
        "queenstown": "D03", "clementi": "D05", "tiong bahru": "D03",
        "orchard": "D09", "river valley": "D09", "newton": "D11",
        "novena": "D11", "tanglin": "D10", "bukit timah": "D10",
    }
    text_lower = text.lower()
    for area, d in area_map.items():
        if area in text_lower:
            zone = EIP_ZONES.get(d, {"name": "Unknown", "eip": "UNKNOWN", "ethnicity": "Unknown"})
            return d, zone["name"], zone["eip"], zone["ethnicity"]

    return "D??", "Unknown", "UNKNOWN", "Unknown"


def build_shortlist(leads):
    """Score, sort, and format leads into the shortlist."""
    scored = []

    for lead in leads:
        # Skip entries without real price
        pv = lead.get("price_val", 0)
        if pv == 0 or pv > MAX_PRICE:
            continue

        # Ensure district/EIP data
        if "district" not in lead or lead.get("district") == "D??":
            d, d_name, eip, ethnicity = detect_district(
                lead.get("address", ""), lead.get("address", "")
            )
            lead["district"] = d
            lead["district_name"] = d_name
            lead["eip_status"] = eip
            lead["ethnicity"] = ethnicity
        else:
            d = lead.get("district", "D??")
            zone = EIP_ZONES.get(d, {"name": "Unknown", "eip": "UNKNOWN", "ethnicity": "Unknown"})
            lead["district_name"] = zone["name"]
            lead["ethnicity"] = zone.get("ethnicity", "Unknown")

        lead["score"] = score_lead(lead)
        scored.append(lead)

    # Sort: highest score first, then by EIP open (OPEN before CLOSED)
    scored.sort(key=lambda x: (x["score"], x["eip_status"] == "CLOSED"), reverse=True)
    return scored


def format_shortlist(scored_leads, date_str):
    """Generate the MOGUL_SHORTLIST.md content."""
    if not scored_leads:
        return f"# 🏘️ MOGUL SHORTLIST — {date_str}\n\n_No listings match criteria today._\n"

    # Summary stats
    total = len(scored_leads)
    eip_open = sum(1 for l in scored_leads if l.get("eip_status") == "OPEN")
    avg_psf = sum(l.get("psf_val", 0) for l in scored_leads) / max(total, 1)
    districts = sorted(set(l.get("district", "D??") for l in scored_leads))

    lines = [
        f"# 🏘️ MOGUL SHORTLIST — {date_str}",
        "",
        "---",
        "",
        "## 📊 Summary",
        "",
        f"| Metric | Value |",
        f"|---------|-------|",
        f"| Total Listings | {total} |",
        f"| EIP Open Zones | {eip_open} |",
        f"| Avg PSF | ${avg_psf:,.0f} |",
        f"| Districts Covered | {', '.join(districts)} |",
        "",
        "---",
        "",
        "## 🏆 Top Picks",
        "",
    ]

    # Top 5 picks
    for i, lead in enumerate(scored_leads[:5], 1):
        eip_badge = "🟢 OPEN" if lead.get("eip_status") == "OPEN" else "🔴 CLOSED"
        score = lead.get("score", 0)
        stars = "★" * min(int(score / 20), 5)

        lines.extend([
            f"### {i}. {lead.get('address', 'Unknown')}",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| 💰 Price | {lead.get('price', 'N/A')} |",
            f"| 📊 PSF | {lead.get('psf', 'N/A')}/sqft |",
            f"| 🏷️ Type | {lead.get('property_type', 'N/A')} |",
            f"| 🛏️ Bedrooms | {lead.get('bedrooms', 'N/A')} |",
            f"| 🎯 Score | {score}/100 {stars} |",
            f"| 🚨 EIP Zone | {eip_badge} ({lead.get('district', 'D??')}) |",
            f"| 👥 Ethnicity | {lead.get('ethnicity', 'N/A')} |",
            f"| 📅 Captured | {lead.get('timestamp', 'N/A')} |",
            "",
            f"🔗 [View Listing]({lead.get('link', '#')})",
            "",
            "---",
            "",
        ])

    # Full table
    lines.extend([
        "## 📋 All Listings",
        "",
        "| # | Address | Price | PSF | District | EIP | Score |",
        "|---|---------|-------|-----|----------|-----|-------|",
    ])

    for i, lead in enumerate(scored_leads, 1):
        eip = "🟢" if lead.get("eip_status") == "OPEN" else "🔴"
        addr = lead.get("address", "N/A")[:35]
        lines.append(
            f"| {i} | {addr} | {lead.get('price','N/A')} | "
            f"{lead.get('psf','N/A')} | {lead.get('district','D??')} | "
            f"{eip} | {lead.get('score',0)} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "_Generated by Mogul Scout AI · Direct Portal Dump v2 · "
        f"{date_str}_",
        "",
        "🦞",
    ])

    return "\n".join(lines)


def generate_telegram_brief(scored_leads, date_str):
    """Generate a Telegram-ready brief (markdown-lite)."""
    if not scored_leads:
        return f"🏘️ Mogul Shortlist {date_str}\n\nNo listings match criteria today."

    lines = [
        f"🏘️ *MOGUL SHORTLIST* — {date_str}",
        "",
    ]

    for i, lead in enumerate(scored_leads[:3], 1):
        eip = "🟢" if lead.get("eip_status") == "OPEN" else "🔴"
        lines.append(
            f"{i}. {lead.get('address', 'N/A')[:40]}\n"
            f"   💰 {lead.get('price', 'N/A')} | {lead.get('psf', 'N/A')}/psf\n"
            f"   🚨 EIP: {lead.get('district', 'D??')} {eip} | ⭐ {lead.get('score', 0)}/100"
        )
        lines.append("")

    total = len(scored_leads)
    eip_open = sum(1 for l in scored_leads if l.get("eip_status") == "OPEN")
    lines.extend([
        f"─────────────────",
        f"📊 {total} listings | 🟢 {eip_open} EIP-Open | "
        f"Full list: MOGUL_SHORTLIST.md",
    ])

    return "\n".join(lines)


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    date_str = datetime.now().strftime("%B %d, %Y")

    # Load leads
    if not os.path.exists(LEADS_PATH):
        print("❌ property_leads.json not found — run scraper first")
        return

    with open(LEADS_PATH, "r") as f:
        try:
            leads = json.load(f)
        except:
            print("❌ Could not parse property_leads.json")
            return

    print(f"📋 Loaded {len(leads)} leads from buffer")

    # ─── AUTO-RECOVERY: If leads are empty and pipeline_dead, try fallback ───
    recovery_note = ""
    if len(leads) == 0:
        SENTINEL_PATH = os.path.expanduser("~/.pipeline_dead")
        FALLBACK_PATH = os.path.join(WORKSPACE, "fallback_leads.json")
        if os.path.exists(SENTINEL_PATH) and os.path.exists(FALLBACK_PATH):
            try:
                with open(FALLBACK_PATH) as f:
                    fallback = json.load(f)
                if fallback:
                    leads = fallback
                    recovery_note = " [🔄 SRX blocked — used 99.co fallback]"
                    print(f"   🔄 Recovery: loaded {len(fallback)} fallback leads{recovery_note}")
            except Exception as e:
                print(f"   ⚠️  Fallback load failed: {e}")

    # Build shortlist
    scored = build_shortlist(leads)
    print(f"🏆 {len(scored)} listings passed filters")

    # Generate MOGUL_SHORTLIST.md
    content = format_shortlist(scored, date_str)
    with open(SHORTLIST_PATH, "w") as f:
        f.write(content)
    print(f"✅ Shortlist saved: {SHORTLIST_PATH}")

    # Generate Telegram brief
    brief = generate_telegram_brief(scored, date_str)
    brief_path = os.path.join(WORKSPACE, "memory/mogul_brief_latest.md")
    with open(brief_path, "w") as f:
        f.write(brief)

    # Stats
    eip_open = sum(1 for l in scored if l.get("eip_status") == "OPEN")
    print(f"\n📊 Summary:")
    print(f"   Total shortlist: {len(scored)}")
    print(f"   EIP Open: {eip_open}")
    print(f"   EIP Closed: {len(scored) - eip_open}")
    if scored:
        print(f"   Top pick: {scored[0].get('address', 'N/A')} "
              f"@ {scored[0].get('price', 'N/A')} ({scored[0].get('score', 0)}/100)")


if __name__ == "__main__":
    main()
