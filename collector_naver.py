import requests
from supabase import create_client
from datetime import datetime, timezone
import config
import time

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

HEADERS = {
    "X-Naver-Client-Id": config.NAVER_CLIENT_ID,
    "X-Naver-Client-Secret": config.NAVER_CLIENT_SECRET,
}

KR_SUFFIXES = ["", "그룹", "상장", "IPO", "공모주", "청약", "주식"]

def expand_search_terms(company_en, company_zh, ticker):
    terms = set()
    if company_en:
        terms.add(company_en)
        terms.add(company_en + " IPO")
    if company_zh:
        for suffix in KR_SUFFIXES:
            terms.add(company_zh + suffix)
        if company_en:
            terms.add(company_zh + " " + company_en)
    if ticker:
        terms.add(ticker)
    return list(terms)

def is_relevant(title, company_en, company_zh, ticker):
    import re
    title_clean = re.sub(r'<[^>]+>', '', title).lower()
    checks = []
    if company_en:
        checks.append(company_en.lower())
    if company_zh:
        checks.append(company_zh)
    if ticker:
        checks.append(ticker.lower())
    return any(c in title_clean for c in checks)

def search_naver_blog(term, display=100, start=1):
    results = []
    url = f"https://openapi.naver.com/v1/search/blog?query={requests.utils.quote(term)}&display={display}&start={start}&sort=date"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        print(f"  Status: {res.status_code}")
        if res.status_code != 200:
            print(f"  Error: {res.text}")
            return results
        data = res.json()
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "body": item.get("description", ""),
                "url": item.get("link", ""),
                "author": item.get("bloggername", ""),
                "posted_at": item.get("postdate", "")
            })
    except Exception as e:
        print(f"  Error: {e}")
    return results

def parse_naver_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc).isoformat()
    except:
        return datetime.now(timezone.utc).isoformat()

def collect_naver(company_en: str, company_zh: str = "", ticker: str = "", days_back: int = 90, region: str = "KR"):
    collected = 0
    search_terms = expand_search_terms(company_en, company_zh, ticker)

    print(f"\nWill search {len(search_terms)} term variations:")
    for t in search_terms:
        print(f"  - {t}")

    seen_urls = set()

    for term in search_terms:
        print(f"\nSearching Naver Blog for: {term}")
        for start in [1, 101]:
            results = search_naver_blog(term, display=100, start=start)
            print(f"  Found {len(results)} posts (start={start})")

            for post in results:
                if post["url"] in seen_urls:
                    continue
                if not is_relevant(post["title"], company_en, company_zh, ticker):
                    continue

                seen_urls.add(post["url"])
                print(f"  Post: {post['title'][:60]}")

                supabase.table("posts").insert({
                    "source": "naver_blog",
                    "region": region,
                    "language": "ko",
                    "company": company_en,
                    "title": post["title"],
                    "body": post["body"],
                    "url": post["url"],
                    "author": post["author"],
                    "posted_at": parse_naver_date(post["posted_at"]),
                    "source_weight": config.SOURCE_WEIGHTS["naver_blog"]
                }).execute()
                collected += 1

            time.sleep(0.5)

    print(f"\nDone. Collected {collected} posts for '{company_en}'.")

if __name__ == "__main__":
    company_en = input("English name: ")
    company_zh = input("Local language name (press Enter to skip): ")
    ticker = input("Ticker / code (press Enter to skip): ")
    region = input("Region (HK/JP/KR/TW/US): ")
    collect_naver(company_en, company_zh, ticker, region=region)