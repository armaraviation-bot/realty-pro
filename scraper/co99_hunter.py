#!/usr/bin/env python3
"""
99.co HUNTER v1.0 — Fresh Inventory Stream
===========================================
Alternative to SRX when SRX anti-bot triggers.
99.co has different fingerprint → different IP/UA reputation.

Key differences from SRX:
- Different DOM structure
- Different listing URL pattern (listings.99.co)
- Different price/PSF extraction
"""
import json
import asyncio
import os
import re
import random
from datetime import datetime
from playwright.async_api import async_playwright

WORKSPACE = os.path.expanduser("~/.openclaw/workspace/")
SETTINGS_PATH = os.path.join(WORKSPACE, "hunter_settings.json")
LEADS_PATH = os.path.join(WORKSPACE, "property_leads.json")

# EIP Zone Data (same as SRX)
EIP_ZONES = {
    "D01": {"name": "Raffles Place", "eip": "OPEN"},
    "D02": {"name": "Tanjong Pagar", "eip": "OPEN"},
    "D03": {"name": "Queenstown", "eip": "OPEN"},
    "D04": {"name": "Telok Blangah", "eip": "CLOSED"},
    "D05": {"name": "Clementi", "eip": "OPEN"},
    "D06": {"name": "Bukit Merah", "eip": "CLOSED"},
    "D07": {"name": "Tanjong Pagar", "eip": "OPEN"},
    "D08": {"name": "Outram", "eip": "OPEN"},
    "D09": {"name": "River Valley", "eip": "OPEN"},
    "D10": {"name": "Tanglin", "eip": "OPEN"},
    "D11": {"name": "Newton", "eip": "OPEN"},
    "D12": {"name": "Toa Payoh", "eip": "CLOSED"},
    "D13": {"name": "Macpherson", "eip": "CLOSED"},
    "D14": {"name": "Geylang", "eip": "CLOSED"},
    "D15": {"name": "Katong", "eip": "CLOSED"},
    "D16": {"name": "Bedok", "eip": "CLOSED"},
    "D17": {"name": "Changi", "eip": "OPEN"},
    "D18": {"name": "Tampines", "eip": "OPEN"},
    "D19": {"name": "Serangoon", "eip": "OPEN"},
    "D20": {"name": "Ang Mo Kio", "eip": "OPEN"},
    "D21": {"name": "Bishan", "eip": "OPEN"},
    "D22": {"name": "Jurong", "eip": "OPEN"},
    "D23": {"name": "Lim Chu Kang", "eip": "CLOSED"},
    "D24": {"name": "West Coast", "eip": "OPEN"},
    "D25": {"name": "Woodlands", "eip": "OPEN"},
    "D26": {"name": "Mandai", "eip": "OPEN"},
    "D27": {"name": "Seletar", "eip": "OPEN"},
    "D28": {"name": "Sembawang", "eip": "OPEN"},
}

def detect_district(text):
    """Extract district from text (e.g., 'D18 — Treasure at Tampines')"""
    match = re.search(r'\bD(\d+)\b', text)
    if match:
        district = f"D{match.group(1)}"
        zone = EIP_ZONES.get(district, {"name": "Unknown", "eip": "UNKNOWN"})
        return district, zone["name"], zone["eip"]
    return "D??", "Unknown", "UNKNOWN"


async def scrape_listing_detail(page, url, max_price):
    """Visit a 99.co listing URL and extract structured data."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(1.5, 2.5))

        title = await page.title()
        address = title.split("|")[0].strip().split(",")[0].strip() if title else "Unknown"

        district, district_name, eip = detect_district(title)

        # 99.co price selector — try multiple patterns
        price_text = ""
        for selector in ['[class*="price"]', '[class*="Price"]', '[data-testid="price"]', '.price-tag', '[class*="amount"]']:
            el = await page.query_selector(selector)
            if el:
                price_text = (await el.inner_text()).strip()
                break

        price_match = re.search(r'\$?\s?([\d,]+)', price_text)
        if price_match:
            price_val = int(price_match.group(1).replace(",", ""))
        else:
            price_val = 0

        if price_val == 0 or price_val > max_price:
            return None

        # PSF extraction from body
        body_text = await page.inner_text('body')
        psf_matches = re.findall(r'\$?\s?([\d,]+)\s*(?:psf|per sqft|/sqft|psqft)', body_text, re.IGNORECASE)
        if psf_matches:
            psf_val = int(psf_matches[0].replace(",", ""))
            psf_str = f"${psf_val:,}"
        else:
            psf_val = 0
            psf_str = "N/A"

        bedrooms_match = re.search(r'(\d+)\s*(?:bedroom|bed|rm|b\/r)', title + " " + body_text, re.IGNORECASE)
        bedrooms = bedrooms_match.group(1) if bedrooms_match else "N/A"

        if "HDB" in title:
            prop_type = "HDB"
        elif "Condo" in title or "condo" in title.lower():
            prop_type = "Condo"
        else:
            prop_type = "Property"

        return {
            "address": address,
            "district": district,
            "district_name": district_name,
            "eip_status": eip,
            "price": f"${price_val:,}",
            "price_val": price_val,
            "psf": psf_str,
            "psf_val": psf_val,
            "bedrooms": bedrooms,
            "property_type": prop_type,
            "link": url,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": "99CO",
        }

    except Exception as e:
        return None


async def scrape_search_page(page, url):
    """
    Visit a 99.co search page and collect listing URLs.
    99.co listing URLs look like: /listings/... or contain /property/
    """
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(random.uniform(2.5, 4.0))

    all_links = await page.query_selector_all('a[href]')
    listing_urls = set()

    for link in all_links:
        href = await link.get_attribute("href")
        if not href:
            continue

        # 99.co listing patterns
        if any(p in href for p in ["/listings/", "/property/", "/real-estate/"]):
            if "/article/" not in href and "/guide/" not in href and "/blog/" not in href:
                full_url = f"https://www.99.co{href}" if href.startswith("/") else href
                listing_urls.add(full_url)

    return list(listing_urls)


async def run():
    if not os.path.exists(SETTINGS_PATH):
        print("❌ hunter_settings.json not found!")
        return []

    with open(SETTINGS_PATH, "r") as f:
        settings = json.load(f)

    # Build 99.co search URL from settings
    # Map towns to 99.co URL format
    town = settings.get("town", "singapore")
    max_price = settings.get("max_price", 1500000)
    keywords = settings.get("keywords", ["Executive", "Maisonette", "Penthouse"])

    # 99.co search URL pattern
    target_url = f"https://www.99.co/singapore/sale/{town}"

    print(f"🏠 99.co Hunter — {target_url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-SG",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        async def block_ads(route):
            if any(x in route.request.url for x in [
                "googleads", "doubleclick", "taboola",
                "analytics", "facebook", "segment"
            ]):
                await route.abort()
            else:
                await route.continue_()
        await context.route("**/*", block_ads)

        page = await context.new_page()

        listing_urls = await scrape_search_page(page, target_url)
        print(f"   📋 Found {len(listing_urls)} listing URLs from 99.co")

        enriched = []
        page2 = await context.new_page()

        for i, url in enumerate(listing_urls[:12], 1):
            print(f"   [{i}/{len(listing_urls[:12])}] Scraping: {url.split('/')[-1][:50]}")
            data = await scrape_listing_detail(page2, url, max_price)

            if data:
                combined_text = (data["address"] + " " + data.get("property_type", "")).lower()
                if any(k.lower() in combined_text for k in keywords):
                    data["priority"] = "high"
                else:
                    data["priority"] = "medium"

                print(
                    f"      ✓ {data['address'][:45]} | {data['price']} | "
                    f"{data['psf']} PSF | {data['district']} | EIP:{data['eip_status']}"
                )
                enriched.append(data)
            else:
                print(f"      ✗ Skipped/over-budget")

            await asyncio.sleep(random.uniform(1.0, 2.0))

        await page2.close()
        await browser.close()

    # Save leads
    if enriched:
        existing = []
        if os.path.exists(LEADS_PATH):
            with open(LEADS_PATH, "r") as f:
                try:
                    existing = json.load(f)
                except:
                    existing = []

        existing_urls = {l["link"] for l in existing if l.get("link")}
        new_leads = [l for l in enriched if l["link"] not in existing_urls]

        combined = existing + new_leads
        with open(LEADS_PATH, "w") as f:
            json.dump(combined, f, indent=2)

        print(f"\n✅ 99.co captured {len(new_leads)} new leads ({len(enriched)} enriched from {len(listing_urls)} URLs)")
        print(f"   Total in buffer: {len(combined)}")
    else:
        print("\n⚠️ No leads captured from 99.co — check URL or pricing")

    return enriched


if __name__ == "__main__":
    asyncio.run(run())
