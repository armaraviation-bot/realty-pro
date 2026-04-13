#!/usr/bin/env python3
"""
Active Scout Protocol 🏹
Proactive property lead hunting using Brave Search API.
Bypasses anti-bot scraping by querying Brave Search directly.

Trigger: Morning (07:30 SGT) or when passive scraping returns 0 leads
Action: Search for distress/EIP/MOP keywords, parse listings, push to Sheets

SMART SCOUT SIESTA (v2 - 2026-03-18):
- 6-hour keyword cooldowns (same keyword only every 6hrs)
- Blocked hours: 23:00-06:00 SGT (nighttime)
- Pre-Sheets deduplication (already implemented)
"""
import json
import os
import re
import subprocess
from datetime import datetime
from urllib.parse import quote

WORKSPACE = os.path.expanduser("~/.openclaw/workspace/")
LEADS_PATH = os.path.join(WORKSPACE, "property_leads.json")
LOG_PATH = os.path.join(WORKSPACE, "memory/active_scout_log.md")
COOLDOWN_PATH = os.path.join(WORKSPACE, "memory/scout_cooldowns.json")
WATCHDOG_PATH = os.path.join(WORKSPACE, "skills/realty-pro/scout_watchdog.json")

# Brave Search API Key (from OpenClaw config)
BRAVE_API_KEY = "BSAJJKDu987FsYMzZKpNhyU1tSo5NLI"

# Search keywords - high-value distress signals
SEARCH_QUERIES = [
    "distress sale singapore property 2026",
    "EIP quota trap singapore condo",
    "MOP minimum occupation period singapore resale",
    "foreclosure singapore property bargain",
    "below market value condo singapore",
    "urgent sale singapore HDB executive",
    "cancellation unit singapore condo",
    "seller willing to pay BSD singapore",
]

# Smart Scout Siesta settings
KEYWORD_COOLDOWN_HOURS = 6
ALLOWED_HOURS = (6, 22)  # 6am - 10pm SGT only

# MOGUL QUALITY GATE - Domain Whitelist
# Only accept leads from trusted property portals
QUALITY_DOMAINS = [
    # Primary Property Portals
    "propertyguru.com",
    "99.co", 
    "srx.com.sg",
    "propnex.com",
    "orangeTee.com",
    "ERA REALTY",
    "cpriop",
    # News/Authority (property sections)
    "businesstimes.com.sg/property",
    "straitstimes.com/property",
    "todayonline.com/property",
    "channelnewsasia.com/property",
    " CNA ",
    # Government/Authority
    "hdb.gov.sg",
    "ura.gov.sg",
    "singstat.gov.sg",
]

# MOGUL QUALITY GATE - Mandatory Fields
REQUIRED_FIELDS = ["price", "address"]  # price must be present, address must be meaningful

def log(message):
    """Log to console and file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"[{timestamp}] {message}"
    print(entry)
    
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\n")

def load_cooldowns():
    """Load keyword cooldowns from file"""
    if os.path.exists(COOLDOWN_PATH):
        with open(COOLDOWN_PATH, "r") as f:
            return json.load(f)
    return {}

def save_cooldowns(cooldowns):
    """Save keyword cooldowns to file"""
    with open(COOLDOWN_PATH, "w") as f:
        json.dump(cooldowns, f, indent=2)

def is_keyword_on_cooldown(keyword, cooldowns):
    """Check if keyword is still in cooldown period"""
    if keyword not in cooldowns:
        return False
    last_searched = datetime.fromisoformat(cooldowns[keyword])
    hours_since = (datetime.now() - last_searched).total_seconds() / 3600
    return hours_since < KEYWORD_COOLDOWN_HOURS

def is_scout_time_allowed():
    """Check if we're in allowed scout hours (6am-10pm SGT)"""
    now = datetime.now()
    hour = now.hour
    return ALLOWED_HOURS[0] <= hour < ALLOWED_HOURS[1]

def get_filtered_queries(cooldowns):
    """Return queries that are NOT on cooldown"""
    allowed = []
    skipped = []
    for query in SEARCH_QUERIES:
        if is_keyword_on_cooldown(query, cooldowns):
            skipped.append(query)
        else:
            allowed.append(query)
    return allowed, skipped

def is_trusted_domain(url):
    """Check if URL is from a whitelisted property portal"""
    if not url:
        return False
    url_lower = url.lower()
    return any(domain in url_lower for domain in QUALITY_DOMAINS)

def passes_quality_gate(lead):
    """MOGUL QUALITY GATE - Validate lead meets minimum quality standards"""
    url = lead.get("link", "")
    
    # Check 1: Must be from trusted domain (news ok if from trusted source)
    is_trusted = is_trusted_domain(url)
    
    # Check 2: Must have valid price (relaxed for news/trusted sources)
    price = lead.get("price", "TBA")
    has_price = price != "TBA" and price
    
    # Check 3: Must have meaningful address
    address = lead.get("address", "").strip()
    has_address = len(address) >= 5 and address != "TBA"
    
    # Pass conditions:
    # - Has price + address (full listing)
    # - OR is from trusted domain + has address (news/authority)
    if has_price and has_address:
        return True, "full_listing"
    elif is_trusted and has_address:
        return True, "trusted_news"
    
    # Rejection reasons
    if not is_trusted:
        return False, "untrusted_domain"
    if not has_price:
        return False, "no_price"
    if not has_address:
        return False, "no_address"
    
    return False, "unknown"

def generate_quality_report(all_leads, filtered_leads):
    """Generate LEAD_QUALITY_REPORT.md for B2B showcase"""
    rejected = [l for l in all_leads if l not in filtered_leads]
    
    report = f"""# LEAD QUALITY REPORT
## Generated: {datetime.now().strftime("%Y-%m-%d %H:%M SGT")}

### SUMMARY
- Total Results: {len(all_leads)}
- Passed Quality Gate: {len(filtered_leads)}
- Rejected: {len(rejected)}
- Pass Rate: {len(filtered_leads)/len(all_leads)*100:.1f}%

### REJECTION REASONS
"""
    # Count rejection reasons
    reasons = {}
    for lead in rejected:
        _, reason = passes_quality_gate(lead)
        reasons[reason] = reasons.get(reason, 0) + 1
    
    for reason, count in reasons.items():
        report += f"- {reason}: {count}\n"
    
    report += """
### PASSED LEADS (B2B Ready)
"""
    for i, lead in enumerate(filtered_leads, 1):
        report += f"""
#### {i}. {lead.get('address', 'N/A')}
- Price: {lead.get('price', 'N/A')}
- Source: {lead.get('link', 'N/A')}
- Priority: {lead.get('priority', 'medium')}
- Keywords: {', '.join(lead.get('keywords_matched', []))}
"""
    
    report += """
---
*Generated by Mogul Quality Gate v1*
"""
    
    # Save report
    report_path = os.path.join(WORKSPACE, "LEAD_QUALITY_REPORT.md")
    with open(report_path, "w") as f:
        f.write(report)
    
    return report_path

def search_web_brave(query, count=5):
    """Use Brave Search API directly"""
    try:
        import requests
        
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": BRAVE_API_KEY
        }
        params = {
            "q": query,
            "count": count
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data.get("web", {}).get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", "")
                })
            return results
        elif response.status_code == 401:
            log("   → Brave API key invalid")
            return []
        else:
            log(f"   → Brave API error: {response.status_code}")
            return []
            
    except ImportError:
        log("   → requests library not available")
        return []
    except Exception as e:
        log(f"   → Search error: {e}")
        return []

def parse_lead_from_result(result):
    """Convert search result into lead format"""
    title = result.get("title", "")
    snippet = result.get("snippet", "")
    url = result.get("url", "")
    
    # Clean up title (remove external content markers)
    title = re.sub(r'<<<.*?>>>', '', title).strip()
    snippet = re.sub(r'<<<.*?>>>', '', snippet).strip()
    
    # Extract potential price
    price_match = re.search(r'\$[\d,]+(?:\.\d{2})?(?:K|M|m|k)?', title + " " + snippet)
    price = price_match.group(0) if price_match else "TBA"
    
    # Extract location/address hints
    location = title.split("|")[0] if "|" in title else title[:60]
    
    lead = {
        "source": "active_scout",
        "address": location.strip(),
        "price": price,
        "description": snippet[:200] if snippet else "",
        "link": url,
        "scout_date": datetime.now().strftime("%Y-%m-%d"),
        "keywords_matched": [],
        "priority": "high" if any(k in snippet.lower() for k in ["urgent", "bargain", "distress", "below"]) else "medium"
    }
    
    return lead

def ensure_watchdog_exists():
    """SCOUT WATCHDOG PROTOCOL: Self-initialize watchdog file on first run if absent"""
    if os.path.exists(WATCHDOG_PATH):
        return
    log("🐕 SCOUT WATCHDOG: First run — self-initializing watchdog file")
    import pathlib
    skill_dir = os.path.dirname(WATCHDOG_PATH)
    os.makedirs(skill_dir, exist_ok=True)
    initial_watchdog = {
        "meta": {
            "version": "1.0",
            "description": "Scout Watchdog tracking — auto-initialized by active_scout.py",
            "created": datetime.now().isoformat() + "Z",
            "last_updated": datetime.now().isoformat() + "Z",
            "auto_created": True
        },
        "last_scout_run": None,
        "consecutive_empty_runs": 0,
        "health_status": "HEALTHY"
    }
    with open(WATCHDOG_PATH, "w") as f:
        json.dump(initial_watchdog, f, indent=2)
    log(f"   → Watchdog initialized at {WATCHDOG_PATH}")

def update_watchdog(run_result):
    """Update watchdog file after each scout run"""
    try:
        if os.path.exists(WATCHDOG_PATH):
            with open(WATCHDOG_PATH, "r") as f:
                wd = json.load(f)
        else:
            wd = {"meta": {}, "last_scout_run": None, "consecutive_empty_runs": 0, "health_status": "HEALTHY"}
        
        wd["meta"]["last_updated"] = datetime.now().isoformat() + "Z"
        wd["last_scout_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " SGT"
        wd["last_run_result"] = run_result
        
        new_leads = run_result.get("new_leads", 0)
        if new_leads == 0:
            wd["consecutive_empty_runs"] = wd.get("consecutive_empty_runs", 0) + 1
        else:
            wd["consecutive_empty_runs"] = 0
        
        if wd["consecutive_empty_runs"] >= 3:
            wd["health_status"] = "ALERT — 3+ consecutive empty runs — scraper may be broken"
        elif wd["consecutive_empty_runs"] >= 1:
            wd["health_status"] = "WARNING — empty run detected"
        else:
            wd["health_status"] = "HEALTHY"
        
        with open(WATCHDOG_PATH, "w") as f:
            json.dump(wd, f, indent=2)
    except Exception as e:
        log(f"   → Watchdog update failed: {e}")

def run_active_scout():
    """Main Active Scout execution"""
    log("=" * 50)
    log("🎯 ACTIVE SCOUT PROTOCOL STARTING")
    log("=" * 50)
    
    # SCOUT WATCHDOG: Self-initialize on first run
    ensure_watchdog_exists()
    
    # Smart Scout Siesta: Check time restrictions
    if not is_scout_time_allowed():
        hour = datetime.now().hour
        log(f"\n🌙 SIESTA MODE: Outside allowed hours ({hour}:00)")
        log(f"   → Scout runs blocked between 11pm-6am SGT")
        log(f"   → Next available window: 6am SGT")
        return {"status": "blocked", "reason": "outside_hours", "hour": hour}
    
    # Load cooldowns
    cooldowns = load_cooldowns()

    # PIPELINE DEAD MAN'S SWITCH: Log if SRX pipeline is down
    # Active Scout uses Brave Search (not SRX) so it still works,
    # but downstream Sheets output should note the degraded state
    SENTINEL_PATH = os.path.expanduser("~/.pipeline_dead")
    if os.path.exists(SENTINEL_PATH):
        try:
            with open(SENTINEL_PATH) as f:
                sentinel_data = json.load(f)
            reason = sentinel_data.get("reason", "unknown")
            triggered = sentinel_data.get("triggered_at", "unknown")
        except:
            reason = "unknown"
            triggered = "unknown"
        log(f"\n⚠️  PIPELINE DEGRADED — SRX scraper failed at {triggered}")
        log(f"   Reason: {reason}")
        log(f"   → Brave Search still operational (this scout is OK)")
        log(f"   → Sheets output will use fallback leads if SRX leads are 0")
    
    
    # Filter queries by cooldown
    allowed_queries, skipped_queries = get_filtered_queries(cooldowns)
    
    log(f"\n🕐 Time Check: PASSED ({datetime.now().hour}:00 SGT)")
    log(f"📋 Query Pool: {len(SEARCH_QUERIES)} total, {len(allowed_queries)} active, {len(skipped_queries)} on cooldown")
    
    if not allowed_queries:
        log(f"\n⏳ All keywords on cooldown. Skipping scout run.")
        return {"status": "blocked", "reason": "all_on_cooldown"}
    
    all_leads = []
    keywords_found = []
    
    # Run searches for each allowed query
    for query in allowed_queries:
        log(f"\n🔍 Searching: {query}")
        results = search_web_brave(query)
        
        if results:
            keywords_found.append(query)
            # Update cooldown for this keyword
            cooldowns[query] = datetime.now().isoformat()
            for result in results:
                lead = parse_lead_from_result(result)
                lead["keywords_matched"] = [query]
                all_leads.append(lead)
            log(f"   → Found {len(results)} results")
        else:
            log(f"   → No results")
    
    # Save updated cooldowns
    save_cooldowns(cooldowns)
    
    # Load existing leads
    existing_leads = []
    if os.path.exists(LEADS_PATH):
        with open(LEADS_PATH, "r") as f:
            try:
                existing_leads = json.load(f)
            except:
                existing_leads = []
    
    # Deduplicate against existing
    existing_urls = {l.get("link", "") for l in existing_leads if l.get("link")}
    new_leads = [l for l in all_leads if l.get("link") and l["link"] not in existing_urls]
    
    # Also dedupe among new leads
    seen_urls = set()
    unique_new_leads = []
    for lead in new_leads:
        if lead.get("link") and lead["link"] not in seen_urls:
            seen_urls.add(lead["link"])
            unique_new_leads.append(lead)
    
    # MOGUL QUALITY GATE - Filter leads
    quality_passed = []
    quality_rejected = []
    for lead in unique_new_leads:
        passed, reason = passes_quality_gate(lead)
        if passed:
            quality_passed.append(lead)
        else:
            quality_rejected.append({"lead": lead, "reason": reason})
    
    log(f"\n🚧 MOGUL QUALITY GATE:")
    log(f"   • Raw new leads: {len(unique_new_leads)}")
    log(f"   • Passed: {len(quality_passed)}")
    log(f"   • Rejected: {len(quality_rejected)}")
    
    # Generate quality report
    if quality_passed or quality_rejected:
        report_path = generate_quality_report(unique_new_leads, quality_passed)
        log(f"   • Report: {report_path}")
    
    # Use quality-passed leads only
    final_leads = quality_passed
    
    # Combine
    combined_leads = existing_leads + final_leads
    
    # Save
    with open(LEADS_PATH, "w") as f:
        json.dump(combined_leads, f, indent=2)
    
    log(f"\n📊 SUMMARY:")
    log(f"   • Queries run: {len(SEARCH_QUERIES)}")
    log(f"   • Keywords with results: {len(keywords_found)}")
    log(f"   • Total results: {len(all_leads)}")
    log(f"   • New unique leads: {len(unique_new_leads)}")
    log(f"   • Quality-gated leads: {len(final_leads)}")
    log(f"   • Total in buffer: {len(combined_leads)}")
    
    # Push to sheets if we have quality leads
    if final_leads:
        log(f"\n📤 Pushing {len(final_leads)} quality leads to Sheets...")
        push_result = subprocess.run(
            ["python3", f"{WORKSPACE}skills/realty-pro/sheets/push_to_sheet.py"],
            capture_output=True,
            text=True,
            timeout=60
        )
        log(f"   → {push_result.stdout.strip()}")
    else:
        log(f"\n⚠️ No quality leads to push")
    
    result = {
        "queries_run": len(SEARCH_QUERIES),
        "keywords_found": keywords_found,
        "total_results": len(all_leads),
        "new_leads": len(final_leads),
        "total_in_buffer": len(combined_leads)
    }
    
    # SCOUT WATCHDOG: Record this run
    update_watchdog(result)
    log(f"   🐕 Watchdog updated: {result.get('new_leads', 0)} new leads")
    
    return result

if __name__ == "__main__":
    result = run_active_scout()
    print(f"\n{'='*50}")
    if result.get("status") == "blocked":
        print(f"⏸️  Scout Blocked: {result.get('reason', 'unknown')}")
    else:
        print(f"✅ Active Scout Complete")
        print(f"   New leads: {result['new_leads']}")
        print(f"   Total buffer: {result['total_in_buffer']}")
