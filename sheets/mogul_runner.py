#!/usr/bin/env python3
"""
Mogul Scout Runner with Caching
- Checks if scrape was done recently
- Only scrapes if cache is stale (>24 hours) or doesn't exist
"""
import json, os, sys
from datetime import datetime, timedelta

workspace = os.path.expanduser("~/.openclaw/workspace/")
leads_path = os.path.join(workspace, "property_leads.json")
cache_meta_path = os.path.join(workspace, "property_cache_meta.json")

CACHE_HOURS = 24

def check_cache():
    """Check if we have valid cached data"""
    # Check if leads file exists
    if not os.path.exists(leads_path):
        return False, "No leads file found"
    
    # Check if cache metadata exists
    if not os.path.exists(cache_meta_path):
        # Old leads file exists but no metadata - check its age
        mtime = os.path.getmtime(leads_path)
        age_hours = (datetime.now().timestamp() - mtime) / 3600
        if age_hours < CACHE_HOURS:
            return True, f"Using existing leads ({age_hours:.1f}h old)"
        return False, f"Leads file is {age_hours:.1f}h old"
    
    # Check metadata
    with open(cache_meta_path, 'r') as f:
        meta = json.load(f)
    
    last_scrape = datetime.fromisoformat(meta.get('last_scrape', '2020-01-01'))
    age = datetime.now() - last_scrape
    
    if age < timedelta(hours=CACHE_HOURS):
        return True, f"Cache valid ({age.total_seconds()/3600:.1f}h old)"
    
    return False, f"Cache stale ({age.total_seconds()/3600:.1f}h old)"

def update_cache_meta():
    """Update cache metadata"""
    meta = {
        'last_scrape': datetime.now().isoformat(),
        'leads_count': 0
    }
    
    # Count leads if file exists
    if os.path.exists(leads_path):
        with open(leads_path, 'r') as f:
            leads = json.load(f)
            meta['leads_count'] = len(leads)
    
    with open(cache_meta_path, 'w') as f:
        json.dump(meta, f, indent=2)

def main():
    print("🕵️ Mogul Scout Runner with Smart Caching")
    print("=" * 50)
    
    # Check cache
    cache_valid, message = check_cache()
    print(f"📋 Cache check: {message}")
    
    if cache_valid:
        print("✅ Using cached data - skipping scrape!")
        print(f"📊 Leads file: {leads_path}")
        
        # Show quick stats
        if os.path.exists(leads_path):
            with open(leads_path, 'r') as f:
                leads = json.load(f)
                print(f"📈 {len(leads)} leads available")
        return 0
    
    print("⏳ Cache stale or missing - running scraper...")
    print()
    
    # Run the scraper
    import subprocess
    
    # Get python from venv
    venv_python = "/home/admin/venv/bin/python3"
    
    result = subprocess.run(
        [venv_python, "/home/admin/property_hunter.py"],
        cwd="/home/admin",
        env={**os.environ, 'PATH': os.environ.get('PATH', '')}
    )
    
    if result.returncode == 0:
        print()
        print("✅ Scraper completed successfully!")
        update_cache_meta()
        
        # Show stats
        if os.path.exists(leads_path):
            with open(leads_path, 'r') as f:
                leads = json.load(f)
                print(f"📈 Captured {len(leads)} leads")
        return 0
    else:
        print("❌ Scraper failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
