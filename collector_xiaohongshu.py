import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from supabase import create_client
from datetime import datetime, timezone
import config
import json
import os

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
COOKIES_FILE = "xiaohongshu_cookies.json"

async def load_cookies(context):
    if os.path.exists(COOKIES_FILE):
        with open(COOKIES_FILE, 'r') as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        print("Xiaohongshu cookies loaded.")
        return True
    return False

async def scrape_xiaohongshu(company_en, company_zh, ticker, days_back=30):
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
        await load_cookies(context)
        
        queries = [company_en]
        if company_zh:
            queries.append(company_zh)
        if ticker:
            queries.append(ticker)
        
        for query in queries:
            if not query:
                continue
            print(f"Searching Xiaohongshu for: {query}")
            
            await page.goto(f"https://www.xiaohongshu.com/search_result?keyword={query}&type=51")
            await page.wait_for_timeout(4000)
            
            try:
                items = await page.query_selector_all('section.note-item, .feeds-page .note-item, [class*="note-item"]')
                
                if not items:
                    items = await page.query_selector_all('a[href*="/explore/"]')
                
                for item in items[:15]:
                    try:
                        title_el = await item.query_selector('a[title], .title, span')
                        body_el = await item.query_selector('p, .desc')
                        link_el = await item.query_selector('a')
                        
                        title = await title_el.inner_text() if title_el else ""
                        body = await body_el.inner_text() if body_el else ""
                        href = await link_el.get_attribute('href') if link_el else ""
                        url = f"https://www.xiaohongshu.com{href}" if href and href.startswith('/') else href
                        
                        if not title and not body:
                            continue
                        
                        posts.append({
                            "source": "xiaohongshu",
                            "region": "HK",
                            "language": "zh",
                            "company": company_en,
                            "title": title.strip(),
                            "body": body.strip(),
                            "url": url,
                            "author": "",
                            "posted_at": datetime.now(timezone.utc).isoformat(),
                            "collected_at": datetime.now(timezone.utc).isoformat(),
                            "source_weight": config.SOURCE_WEIGHTS.get("xiaohongshu", 0.8),
                            "sentiment_score": None,
                            "sentiment_label": None,
                            "keywords": [],
                            "relevance_tag": None,
                            "conviction": None,
                        })
                    except:
                        continue
            except Exception as e:
                print(f"Error scraping Xiaohongshu: {e}")
        
        await browser.close()
    
    print(f"Xiaohongshu collected {len(posts)} posts")
    
    if posts:
        supabase.table("posts").insert(posts).execute()
    
    return posts

if __name__ == "__main__":
    company_en = input("Company name (English): ")
    company_zh = input("Local name: ")
    ticker = input("Ticker: ")
    asyncio.run(scrape_xiaohongshu(company_en, company_zh, ticker))