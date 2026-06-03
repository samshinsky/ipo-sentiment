import requests
from bs4 import BeautifulSoup
from supabase import create_client
from datetime import datetime, timezone
import config
import time

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

BASE_URL = "https://www.dcard.tw/_api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.dcard.tw/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

TW_SUFFIXES = ["集團", "控股", "上市", "IPO", "興櫃", "新股"]

def expand_search_terms(company_en, company_zh, ticker):
    terms = set()
    if company_en:
        terms.add(company_en)
        terms.add(company_en + " IPO")
    if company_zh:
        for suffix in TW_SUFFIXES:
            terms.add(company_zh + suffix)
        if company_en:
            terms.add(company_zh + " " + company_en)
    if ticker:
        terms.add(ticker)
    return list(terms)

def is_relevant(title, company_en, company_zh, ticker):
    title_lower = title.lower()
    checks = []
    if company_en:
        checks.append(company_en.lower())
    if company_zh:
        checks.append(company_zh)
    if ticker:
        checks.append(ticker.lower())
    return any(c in title_lower for c in checks)

def search_dcard(term, forum="stock"):
    results = []
    url = f"{BASE_URL}/search/posts?query={requests.utils.quote(term)}&forum={forum}&limit=30"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        print(f"  Status: {res.status_code}")
        if res.status_code != 200:
            return results
        data = res.json()
        for post in data:
            results.append({
                "id": post.get("id"),
                "title": post.get("title", ""),
                "body": post.get("excerpt", ""),
                "url": f"https://www.dcard.tw/f/{forum}/p/{post.get('id')}",
                "author": post.get("school", ""),
                "created_at": post.get("createdAt", "")
            })
    except Exception as e:
        print(f"  Error: {e}")
    return results

def get_comments(post_id):
    comments = []
    url = f"{BASE_URL}/posts/{post_id}/comments?limit=100"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return comments
        data = res.json()
        for comment in data:
            comments.append({
                "body": comment.get("content", ""),
                "author": comment.get("school", ""),
                "created_at": comment.get("createdAt", "")
            })
    except Exception as e:
        print(f"  Error getting comments: {e}")
    return comments

def collect_dcard(company_en: str, company_zh: str = "", ticker: str = "", days_back: int = 90, region: str = "TW"):
    collected = 0
    search_terms = expand_search_terms(company_en, company_zh, ticker)

    print(f"\nWill search {len(search_terms)} term variations:")
    for t in search_terms:
        print(f"  - {t}")

    seen_ids = set()
    forums = ["stock", "finance", "trending"]

    for forum in forums:
        for term in search_terms:
            print(f"\nSearching Dcard /{forum}/ for: {term}")
            posts = search_dcard(term, forum)
            print(f"  Found {len(posts)} posts")

            for post in posts:
                if post["id"] in seen_ids:
                    continue
                if not is_relevant(post["title"], company_en, company_zh, ticker):
                    print(f"  Skipping irrelevant: {post['title'][:50]}")
                    continue

                seen_ids.add(post["id"])
                print(f"  Post: {post['title'][:60]}")

                supabase.table("posts").insert({
                    "source": "dcard",
                    "region": region,
                    "language": "zh",
                    "company": company_en,
                    "title": post["title"],
                    "body": post["body"],
                    "url": post["url"],
                    "author": post["author"],
                    "posted_at": post["created_at"] or datetime.now(timezone.utc).isoformat(),
                    "source_weight": config.SOURCE_WEIGHTS["dcard"]
                }).execute()
                collected += 1

                comments = get_comments(post["id"])
                print(f"    Got {len(comments)} comments")
                for comment in comments:
                    if not comment["body"]:
                        continue
                    supabase.table("posts").insert({
                        "source": "dcard",
                        "region": region,
                        "language": "zh",
                        "company": company_en,
                        "title": None,
                        "body": comment["body"],
                        "url": post["url"],
                        "author": comment["author"],
                        "posted_at": comment["created_at"] or datetime.now(timezone.utc).isoformat(),
                        "source_weight": config.SOURCE_WEIGHTS["dcard"]
                    }).execute()
                    collected += 1

                time.sleep(1)

    print(f"\nDone. Collected {collected} posts for '{company_en}'.")

if __name__ == "__main__":
    company_en = input("English name: ")
    company_zh = input("Local language name (press Enter to skip): ")
    ticker = input("Ticker / code (press Enter to skip): ")
    region = input("Region (HK/JP/KR/TW/US): ")
    collect_dcard(company_en, company_zh, ticker, region=region)