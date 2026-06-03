import requests
from bs4 import BeautifulSoup
from supabase import create_client
from datetime import datetime, timezone
import config
import time

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.jisilu.cn/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

CN_SUFFIXES = ["", "IPO", "打新", "申购", "新股", "上市", "集团", "控股"]

def expand_search_terms(company_en, company_zh, ticker):
    terms = set()
    if company_en:
        terms.add(company_en)
        terms.add(company_en.replace(" ", ""))
    if company_zh:
        for suffix in CN_SUFFIXES:
            terms.add(company_zh + suffix)
    if ticker:
        terms.add(ticker)
    return list(terms)

def is_relevant(text, company_en, company_zh, ticker):
    text_lower = text.lower()
    checks = []
    if company_en:
        checks.append(company_en.lower())
        checks.append(company_en.lower().replace(" ", ""))
    if company_zh:
        checks.append(company_zh)
    if ticker:
        checks.append(ticker.lower())
    return any(c in text_lower for c in checks)

def search_jisilu(term):
    results = []
    url = f"https://www.jisilu.cn/search/result/?wd={requests.utils.quote(term)}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        print(f"  Status: {res.status_code}")
        if res.status_code != 200:
            return results
        soup = BeautifulSoup(res.text, "html.parser")
        for link in soup.select("a[href*='/question/']"):
            href = link.get("href", "")
            title = link.text.strip()
            if title and len(title) > 3:
                if not href.startswith("http"):
                    href = "https://www.jisilu.cn" + href
                results.append({"url": href, "title": title})
        for link in soup.select("a[href*='/topic/']"):
            href = link.get("href", "")
            title = link.text.strip()
            if title and len(title) > 3:
                if not href.startswith("http"):
                    href = "https://www.jisilu.cn" + href
                results.append({"url": href, "title": title})
    except Exception as e:
        print(f"  Error: {e}")
    return results

def get_thread_posts(url):
    posts = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return posts
        soup = BeautifulSoup(res.text, "html.parser")
        for post in soup.select("div.answer-item, div.comment-item, div.post-item"):
            body_el = post.select_one("div.content, div.answer-content, p")
            author_el = post.select_one("a.username, span.username")
            if body_el:
                posts.append({
                    "body": body_el.get_text(separator=" ").strip(),
                    "author": author_el.text.strip() if author_el else ""
                })
        if not posts:
            for div in soup.select("div.wiki-content, div.topic-content"):
                text = div.get_text(separator=" ").strip()
                if text and len(text) > 10:
                    posts.append({"body": text, "author": ""})
    except Exception as e:
        print(f"  Error fetching thread: {e}")
    return posts

def collect_jisilu(company_en: str, company_zh: str = "", ticker: str = "", days_back: int = 90, region: str = "HK"):
    collected = 0
    search_terms = expand_search_terms(company_en, company_zh, ticker)

    print(f"\nWill search {len(search_terms)} term variations:")
    for t in search_terms:
        print(f"  - {t}")

    seen_urls = set()

    for term in search_terms:
        print(f"\nSearching Jisilu for: {term}")
        threads = search_jisilu(term)
        print(f"  Found {len(threads)} threads")

        for thread in threads:
            if thread["url"] in seen_urls:
                continue
            if not is_relevant(thread["title"], company_en, company_zh, ticker):
                print(f"  Skipping irrelevant: {thread['title'][:50]}")
                continue

            seen_urls.add(thread["url"])
            print(f"  Thread: {thread['title'][:60]}")

            posts = get_thread_posts(thread["url"])
            print(f"    Got {len(posts)} posts")

            for i, post in enumerate(posts):
                if not post["body"]:
                    continue
                supabase.table("posts").insert({
                    "source": "jisilu",
                    "region": region,
                    "language": "zh",
                    "company": company_en,
                    "title": thread["title"] if i == 0 else None,
                    "body": post["body"],
                    "url": thread["url"],
                    "author": post["author"],
                    "posted_at": datetime.now(timezone.utc).isoformat(),
                    "source_weight": config.SOURCE_WEIGHTS["jisilu"]
                }).execute()
                collected += 1

            time.sleep(1)

    print(f"\nDone. Collected {collected} posts for '{company_en}'.")

if __name__ == "__main__":
    company_en = input("English name: ")
    company_zh = input("Local language name (press Enter to skip): ")
    ticker = input("Ticker / code (press Enter to skip): ")
    region = input("Region (HK/JP/KR/TW/US): ")
    collect_jisilu(company_en, company_zh, ticker, region=region)