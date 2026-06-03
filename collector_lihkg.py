import asyncio
import requests
from playwright.async_api import async_playwright
from supabase import create_client
from datetime import datetime, timezone
import config

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

HK_SUFFIXES = ["", "藥房", "集團", "控股", "上市", "IPO", "打新", "新股"]
JP_SUFFIXES = ["", "株式会社", "上場", "IPO", "新規上場"]
KR_SUFFIXES = ["", "그룹", "상장", "IPO", "공모주"]
TW_SUFFIXES = ["", "集團", "控股", "上市", "IPO", "興櫃"]

REGION_SUFFIXES = {
    "HK": HK_SUFFIXES,
    "CN": HK_SUFFIXES,
    "US": ["", "IPO", "上市", "打新"],
    "JP": JP_SUFFIXES,
    "KR": KR_SUFFIXES,
    "TW": TW_SUFFIXES,
}

def expand_search_terms(company_en, company_zh, ticker, region):
    terms = set()
    if company_en:
        terms.add(company_en)
        terms.add(company_en + " IPO")
    if company_zh:
        suffixes = REGION_SUFFIXES.get(region, [""])
        for suffix in suffixes:
            terms.add(company_zh + suffix)
    if ticker:
        terms.add(ticker)
    return list(terms)

async def get_lihkg_cookies():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(locale="zh-HK")
        page = await context.new_page()
        print("Getting LIHKG session cookies...")
        await page.goto("https://lihkg.com", wait_until="networkidle")
        await asyncio.sleep(5)
        cookies = await context.cookies()
        await browser.close()
        return {c['name']: c['value'] for c in cookies}

def api_search(term, cookies, page=1):
    url = f"https://lihkg.com/api_v2/thread/search?q={requests.utils.quote(term)}&page={page}&count=30&order=desc"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://lihkg.com/",
        "Origin": "https://lihkg.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-HK,zh;q=0.9",
        "x-li-device-type": "browser",
    }
    res = requests.get(url, headers=headers, cookies=cookies, timeout=10)
    print(f"  Search status: {res.status_code}")
    if res.status_code == 200:
        try:
            return res.json()
        except:
            print(f"  Response: {res.text[:200]}")
    return None

def api_get_thread(thread_id, cookies, page=1):
    url = f"https://lihkg.com/api_v2/thread/{thread_id}/page/{page}?order=reply_time"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": f"https://lihkg.com/thread/{thread_id}/page/{page}",
        "Origin": "https://lihkg.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-HK,zh;q=0.9",
        "x-li-device-type": "browser",
    }
    res = requests.get(url, headers=headers, cookies=cookies, timeout=10)
    if res.status_code == 200:
        try:
            return res.json()
        except:
            pass
    return None

async def search_lihkg(company_en: str, company_zh: str = "", ticker: str = "", days_back: int = 90, region: str = "HK"):
    collected = 0
    cutoff = datetime.now(timezone.utc).timestamp() - (days_back * 86400)

    search_terms = expand_search_terms(company_en, company_zh, ticker, region)
    print(f"\nWill search {len(search_terms)} term variations:")
    for t in search_terms:
        print(f"  - {t}")

    cookies = await get_lihkg_cookies()
    print(f"\nGot {len(cookies)} cookies")
    print("Waiting 10 seconds before starting searches...")
    await asyncio.sleep(10)

    seen_thread_ids = set()

    for term in search_terms:
        print(f"\nSearching for: {term}")
        await asyncio.sleep(3)
        page = 1
        while True:
            data = api_search(term, cookies, page)
            if not data:
                break

            items = data.get("response", {}).get("items", [])
            if not items:
                print(f"  No results on page {page}")
                break

            print(f"  Found {len(items)} threads on page {page}")

            for thread in items:
                thread_id = thread.get("thread_id")
                created = thread.get("create_time", 0)
                title = thread.get("title", "")

                if thread_id in seen_thread_ids:
                    continue
                seen_thread_ids.add(thread_id)

                if created < cutoff:
                    continue

                print(f"  Thread: {title[:60]}")

                supabase.table("posts").insert({
                    "source": "lihkg",
                    "region": region,
                    "language": "zh",
                    "company": company_en,
                    "title": title,
                    "body": thread.get("first_post", {}).get("msg", ""),
                    "url": f"https://lihkg.com/thread/{thread_id}/page/1",
                    "author": thread.get("user", {}).get("nickname", ""),
                    "posted_at": datetime.fromtimestamp(created, tz=timezone.utc).isoformat(),
                    "source_weight": config.SOURCE_WEIGHTS["lihkg"]
                }).execute()
                collected += 1

                reply_page = 1
                total_pages = thread.get("total_page", 1)
                while reply_page <= total_pages:
                    thread_data = api_get_thread(thread_id, cookies, reply_page)
                    if not thread_data:
                        break
                    replies = thread_data.get("response", {}).get("item_data", [])
                    for reply in replies:
                        body = reply.get("msg", "")
                        if not body:
                            continue
                        reply_time = reply.get("reply_time", 0)
                        supabase.table("posts").insert({
                            "source": "lihkg",
                            "region": region,
                            "language": "zh",
                            "company": company_en,
                            "title": None,
                            "body": body,
                            "url": f"https://lihkg.com/thread/{thread_id}/page/{reply_page}",
                            "author": reply.get("user", {}).get("nickname", ""),
                            "posted_at": datetime.fromtimestamp(reply_time, tz=timezone.utc).isoformat() if reply_time else datetime.now(timezone.utc).isoformat(),
                            "source_weight": config.SOURCE_WEIGHTS["lihkg"]
                        }).execute()
                        collected += 1
                    reply_page += 1
                    await asyncio.sleep(1)

            page += 1
            await asyncio.sleep(3)

    print(f"\nDone. Collected {collected} posts for '{company_en}'.")

if __name__ == "__main__":
    company_en = input("English name: ")
    company_zh = input("Local language name (press Enter to skip): ")
    ticker = input("Ticker / code (press Enter to skip): ")
    region = input("Region (HK/JP/KR/TW/US): ")
    asyncio.run(search_lihkg(company_en, company_zh, ticker, region=region))