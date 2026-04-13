#!/usr/bin/env python3
"""
Morning Property Pulse - Rotating District Scraper
Runs at 06:00 SGT daily to scan 2 fresh districts

AUTO-RECOVERY (Dead Man's Switch):
- After scraping, checks if leads == 0
- If pipeline_dead sentinel exists, fetches from 99.co fallback
- All downstream scripts (mogul_shortlist, push_to_sheet) read from property_leads.json
  which is populated by fallback if SRX is blocked
"""
import json, os, random, asyncio, sys
from datetime import datetime

# Pipeline recovery import
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
try:
    from pipeline_recovery import is_pipeline_dead, get_sentinel_reason, log_recovery, fetch_fallback_leads
except ImportError:
    is_pipeline_dead = lambda: os.path.exists(os.path.expanduser("~/.pipeline_dead"))
    get_sentinel_reason = lambda: "unknown"
    log_recovery = lambda *a, **k: None
    async def fetch_fallback_leads(): return []

# Singapore condo districts (1-28)
DISTRICTS = [
    {"name": "Orchard/River Valley", "url": "https://www.srx.com.sg/search/sale/condo/orchard-river-valley"},
    {"name": "Tanglin/Bukit Timah", "url": "https://www.srx.com.sg/search/sale/condo/tanglin-bukit-timah"},
    {"name": "Newton/Novena", "url": "https://www.srx.com.sg/search/sale/condo/newton-novena"},
    {"name": "Toa Payoh/Balestier", "url": "https://www.srx.com.sg/search/sale/condo/toa-payoh"},
    {"name": "East Coast/Marine Parade", "url": "https://www.srx.com.sg/search/sale/condo/marine-parade"},
    {"name": "Bedok/Upper East Coast", "url": "https://www.srx.com.sg/search/sale/condo/bedok"},
    {"name": "Tampines", "url": "https://www.srx.com.sg/search/sale/condo/tampines"},
    {"name": "Pasir Ris", "url": "https://www.srx.com.sg/search/sale/condo/pasir-ris"},
    {"name": "Changi", "url": "https://www.srx.com.sg/search/sale/condo/changi"},
    {"name": "Loyang", "url": "https://www.srx.com.sg/search/sale/condo/loyang"},
    {"name": "Hougang", "url": "https://www.srx.com.sg/search/sale/condo/hougang"},
    {"name": "Punggol", "url": "https://www.srx.com.sg/search/sale/condo/punggol"},
    {"name": "Sengkang", "url": "https://www.srx.com.sg/search/sale/condo/sengkang"},
    {"name": "Ang Mo Kio", "url": "https://www.srx.com.sg/search/sale/condo/ang-mo-kio"},
    {"name": "Bishan/Braddell", "url": "https://www.srx.com.sg/search/sale/condo/bishan"},
    {"name": "Macpherson", "url": "https://www.srx.com.sg/search/sale/condo/macpherson"},
    {"name": "Geylang", "url": "https://www.srx.com.sg/search/sale/condo/geylang"},
    {"name": "Katong/Joo Chiat", "url": "https://www.srx.com.sg/search/sale/condo/katong"},
    {"name": "Bukit Merah", "url": "https://www.srx.com.sg/search/sale/condo/bukit-merah"},
    {"name": "Queenstown", "url": "https://www.srx.com.sg/search/sale/condo/queenstown"},
    {"name": "Boon Keng", "url": "https://www.srx.com.sg/search/sale/condo/boon-keng"},
    {"name": "Clementi", "url": "https://www.srx.com.sg/search/sale/condo/clementi"},
    {"name": "Dover/Buona Vista", "url": "https://www.srx.com.sg/search/sale/condo/buona-vista"},
    {"name": "Jurong", "url": "https://www.srx.com.sg/search/sale/condo/jurong"},
    {"name": "Tuas", "url": "https://www.srx.com.sg/search/sale/condo/tuas"},
    {"name": "Lim Chu Kang", "url": "https://www.srx.com.sg/search/sale/condo/lim-chu-kang"},
    {"name": "Bukit Panjang", "url": "https://www.srx.com.sg/search/sale/condo/bukit-panjang"},
    {"name": "Choa Chu Kang", "url": "https://www.srx.com.sg/search/sale/condo/choa-chu-kang"},
    {"name": "Kranji", "url": "https://www.srx.com.sg/search/sale/condo/kranji"},
    {"name": "Yishun", "url": "https://www.srx.com.sg/search/sale/condo/yishun"},
    {"name": "Sembawang", "url": "https://www.srx.com.sg/search/sale/condo/sembawang"},
    {"name": "Seletar", "url": "https://www.srx.com.sg/search/sale/condo/seletar"},
]

WORKSPACE = os.path.expanduser("~/.openclaw/workspace/")
SETTINGS_PATH = os.path.join(WORKSPACE, "hunter_settings.json")
LEADS_PATH = os.path.join(WORKSPACE, "property_leads.json")

def get_today_districts():
    """Get 2 districts based on today's date - rotates weekly"""
    today = datetime.now()
    day_of_year = today.timetuple().tm_yday
    
    # Rotate every 3 days to cover all districts in ~6 weeks
    start_idx = (day_of_year // 3) % len(DISTRICTS)
    
    district1 = DISTRICTS[start_idx % len(DISTRICTS)]
    district2 = DISTRICTS[(start_idx + 1) % len(DISTRICTS)]
    
    return [district1, district2]

def update_settings(district):
    """Update hunter_settings.json for a district"""
    settings = {
        "url": district["url"],
        "max_price": 1500000,  # $1.5M default
        "keywords": ["Executive", "Maisonette", "Penthouse", "Dual Key"]
    }
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
    return settings

def generate_brief(leads, recovery_used=False):
    """Generate WhatsApp-ready brief"""
    if not leads:
        return "⚠️ No leads found today. Pipeline may be blocked."
    
    recovery_tag = " [🔄 AUTO-RECOVERY]" if recovery_used else ""
    brief = f"🏠 *Morning Property Pulse* — {datetime.now().strftime('%b %d')}{recovery_tag}\n\n"
    
    # Top 3 picks
    brief += "*🔥 Hot Picks:*\n"
    for lead in leads[:3]:
        brief += f"• {lead.get('address', 'N/A')[:40]}\n"
        brief += f"  💰 {lead.get('price', 'N/A')} | {lead.get('psf', 'N/A')} PSF\n"
        brief += f"  🔗 {lead.get('link', '')[:50]}\n\n"
    
    total = len(leads)
    brief += f"_Scanned {total} listings. Full report in Sheets._"
    
    return brief

# Main execution
if __name__ == "__main__":
    print("🌅 Morning Property Pulse starting...")
    
    districts = get_today_districts()
    print(f"📍 Scanning today: {districts[0]['name']} & {districts[1]['name']}")
    
    all_leads = []
    
    for district in districts:
        print(f"\n🔍 Scanning: {district['name']}")
        update_settings(district)
        
        # Run the scraper
        import subprocess
        result = subprocess.run(
            ["python3", f"{WORKSPACE}skills/realty-pro/scraper/property_hunter.py"],
            capture_output=True,
            text=True,
            timeout=180
        )
        
        # Collect leads
        if os.path.exists(LEADS_PATH):
            with open(LEADS_PATH, "r") as f:
                leads = json.load(f)
                all_leads.extend(leads)
    
    # Deduplicate
    unique_leads = {l['link']: l for l in all_leads}.values()
    unique_leads = list(unique_leads)

    # ─── AUTO-RECOVERY: If SRX returned nothing, try 99.co fallback ───
    recovery_used = False
    if len(unique_leads) == 0 or is_pipeline_dead():
        reason = get_sentinel_reason()
        print(f"\n⚠️  SRX pipeline empty/dead — triggering AUTO-RECOVERY")
        print(f"   Sentinel reason: {reason}")
        
        # Run async fallback fetch
        fallback_leads = asyncio.run(fetch_fallback_leads())
        
        if fallback_leads:
            unique_leads = fallback_leads
            recovery_used = True
            log_recovery("morning_pulse", "99.co_fallback", len(fallback_leads))
            print(f"   ✅ Recovery success: {len(fallback_leads)} fallback leads")
        else:
            # Last resort: pull from existing fallback_leads.json
            fb_path = os.path.join(WORKSPACE, "fallback_leads.json")
            if os.path.exists(fb_path):
                with open(fb_path) as f:
                    fb = json.load(f)
                    if fb:
                        unique_leads = fb
                        recovery_used = True
                        print(f"   🔄 Used pre-fetched fallback: {len(fb)} leads")
    
    # Save combined leads
    with open(LEADS_PATH, "w") as f:
        json.dump(unique_leads, f, indent=2)
    
    # Push to sheets
    print("\n📋 Pushing to Google Sheets...")
    subprocess.run(["python3", f"{WORKSPACE}skills/realty-pro/sheets/push_to_sheet.py"])
    
    # Generate brief
    brief = generate_brief(unique_leads, recovery_used=recovery_used)
    print(f"\n{brief}")
    
    # Save brief
    brief_path = os.path.join(WORKSPACE, "memory/property_brief.md")
    with open(brief_path, "w") as f:
        f.write(brief)
    
    recovery_note = " [AUTO-RECOVERY]" if recovery_used else ""
    print(f"\n✅ Morning Pulse complete! {len(unique_leads)} leads processed.{recovery_note}")
