import json, asyncio, os, re, random
from datetime import datetime
from playwright.async_api import async_playwright

async def run():
    workspace = os.path.expanduser("~/.openclaw/workspace/")
    settings_path = os.path.join(workspace, "hunter_settings.json")
    leads_path = os.path.join(workspace, "property_leads.json")
    
    # Load settings from Gandalf's config
    if not os.path.exists(settings_path):
        print("❌ Error: hunter_settings.json not found!")
        return
        
    with open(settings_path, "r") as f:
        settings = json.load(f)
    
    target_url = settings.get("url")
    max_price = settings.get("max_price", 1500000)
    keywords = settings.get("keywords", ["Maisonette", "Executive"])

    async with async_playwright() as p:
        # STEALTH UPGRADE: Launch with real-world browser settings
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()
        
        try:
            print(f"🧙‍♂️ Gandalf is stealthily visiting: {target_url}")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            
            # HUMAN BEHAVIOR: Random scrolling to trigger lazy-loading
            for _ in range(3):
                await page.mouse.wheel(0, random.randint(800, 1200))
                await asyncio.sleep(random.uniform(2.0, 4.0))
            
            # BROAD MATCH SEARCH: Find all links that look like listings
            links = await page.query_selector_all("a[href*='/listings/']")
            matches = []
            
            for link in links:
                # Get the surrounding text for this link
                parent = await link.evaluate_handle("el => el.closest('div')")
                text = await page.evaluate("el => el.innerText", parent)
                
                # Check for Price and Keywords
                price_match = re.search(r'\$\s?([\d,]+)', text)
                if price_match:
                    price_val = int(price_match.group(1).replace(',', ''))
                    
                    # Apply Filters
                    price_ok = price_val <= max_price
                    keyword_ok = any(k.lower() in text.lower() for k in keywords)
                    
                    if price_ok and keyword_ok:
                        href = await link.get_attribute("href")
                        full_link = f"https://www.srx.com.sg{href}" if href.startswith("/") else href
                        
                        matches.append({
                            "summary": " ".join(text.split())[:120],
                            "price": f"${price_val:,}",
                            "link": full_link,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
                        })

            # Deduplicate results based on the link
            unique_matches = { m['link']: m for m in matches }.values()
            
            with open(leads_path, "w") as f:
                json.dump(list(unique_matches), f, indent=4)
                
            print(f"✅ Success! Captured {len(unique_matches)} properties for the client.")

        except Exception as e:
            print(f"❌ Stealth Error: {e}")
            # Optional: save a screenshot if it fails
            await page.screenshot(path="/home/admin/error_debug.png")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
