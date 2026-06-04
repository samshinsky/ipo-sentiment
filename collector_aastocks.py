import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from supabase import create_client
from datetime import datetime, timezone
import config
import json
import os

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
COOKIES_FILE = "aastocks_cookies.json"

async def save_cookies(context):
    cookies = await context.cookies()
    with open(COOKIES_FILE, 'w') as f:
        json.dump(cookies, f)
    print("AAStocks cookies saved.")

async def load_cookies(context):
    if os.path.exists(COOKIES_FILE):
        with open(COOKIES_FILE, 'r') as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        print("AAStocks cookies loaded.")
        return True
    return False

async def login_aastocks(page, context):
    print("Logging into AAStocks...")
    await page.goto("https://logon.aastocks.com/mainsite/en/login.aspx")
    await page.wait_for_timeout(2000)
    print("Please log in manually in the browser window, then press Enter here...")
    input()
    await save_cookies(context)
    print("AAStocks cookies saved.")
    return True

async def scrape_aastocks(company_en, company_zh, ticker, days_back=30):
    posts = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        
        cookies_loaded = await load_cookies(context)
        if not cookies_loaded:
            logged_in = await login_aastocks(page, context)
            if not logged_in:
                await browser.close()
                return []
        
        queries = [company_en, ticker]
        if company_zh:
            queries.append(company_zh)
        
        for query in queries:
            if not query:
                continue
            print(f"Searching AAStocks for: {query}")
            
            search_url = f"https://www.aastocks.com/en/stocks/analysis/analytic/search.aspx?q={query}"
            await page.goto(search_url)
            await page.wait_for_timeout(3000)
            
            try:
                items = await page.query_selector_all('.news-item, .article-item, tr')
                
                for item in items[:20]:
                    try:
                        title_el = await item.query_selector('a, .title')
                        if not title_el:
                            continue
                        title = await title_el.inner_text()
                        href = await title_el.get_attribute('href') or ""
                        url = f"https://www.aastocks.com{href}" if href.startswith('/') else href
                        
                        if not title or len(title.strip()) < 5:
                            continue
                        
                        posts.append({
                            "source": "aastocks",
                            "region": "HK",
                            "language": "zh",
                            "company": company_en,
                            "title": title.strip(),
                            "body": title.strip(),
                            "url": url,
                            "author": "",
                            "posted_at": datetime.now(timezone.utc).isoformat(),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "source_weight": config.SOURCE_WEIGHTS.get("aastocks", 0.9),
                            "sentiment_score": None,
                            "sentiment_label": None,
                            "keywords": [],
                            "relevance_tag": None,
                            "conviction": None,
                        })
                    except:
                        continue
            except Exception as e:
                print(f"Error scraping AAStocks: {e}")
        
        await browser.close()
    
    print(f"AAStocks collected {len(posts)} posts")
    
    if posts:
        supabase.table("posts").insert(posts).execute()
    
    return posts

if __name__ == "__main__":
    company_en = input("Company name (English): ")
    company_zh = input("Local name: ")
    ticker = input("Ticker: ")
    asyncio.run(scrape_aastocks(company_en, company_zh, ticker))