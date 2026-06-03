import requests
from bs4 import BeautifulSoup
from supabase import create_client
from datetime import datetime, timezone
import config
import time

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://finance.naver.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

KR_SUFFIXES = ["", "그룹", "상장", "IPO", "공모주", "청약", "주식", "기업공개"]

def expand_search_terms(company_en, company_zh, ticker):
    terms = set()
    if company_en:
        terms.add(company_en)
        terms.add(company_en + " IPO")
        terms.add(company_en.replace(" ", ""))
    if company_zh:
        for suffix in KR_SUFFIXES:
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

def search_naver_finance(term):
    results = []
    url = f"https://finance.naver.com/search/searchList.naver?query={requests.utils.quote(term)}&target=discussion"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        print(f"  Status: {res.status_code}")
        if res.status_code != 200:
            return results
        soup = BeautifulSoup(res.text, "html.parser")
        for item in soup.select("div.discussion_list li, ul.lst_discussion li"):
            title_el = item.select_one("a.tit, a.title, dt a")
            if not title_el:
                continue
            title = title_el.text.strip()
            href = title_el.get("href", "")
            if not href.startswith("http"):
                href = "https://finance.naver.com" + href
            if title and len(title) > 3:
                results.append({"url": href, "title": title})
    except Exception as e:
        print(f"  Error: {e}")
    return results

def search_naver_news(term):
    results = []
    url = f"https://openapi.naver.com/v1/search/news?query={requests.utils.quote(term)}&display=100&sort=date"
    headers = {
        "X-Naver-Client-Id": config.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": config.NAVER_CLIENT_SECRET,
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        print(f"  News API status: {res.status_code}")
        if res.status_code != 200:
            return results
        data = res.json()
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "body": item.get("description", ""),
                "url": item.get("link", ""),
                "author": item.get("originallink", ""),
                "posted_at": item.get("pubDate", "")
            })
    except Exception as e:
        print(f"  Error: {e}")
    return results

def get_discussion_posts(url):
    posts = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return posts
        soup = BeautifulSoup(res.text, "html.parser")
        for post in soup.select("div.view_content, div.discuss_view, td.view_content"):
            text = post.get_text(separator="\n").strip()
            if text and len(text) > 5:
                posts.append({"body": text, "author": ""})
        for reply in soup.select("div.reply_content, li.reply_item"):
            text = reply.get_text(separator=" ").strip()
            if text and len(text) > 5:
                posts.append({"body": text, "author": ""})
    except Exception as e:
        print(f"  Error fetching discussion: {e}")
    return posts

def parse_pub_date(date_str):
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str).isoformat()
    except:
        return datetime.now(timezone.utc).isoformat()

def collect_naver_finance(company_en: str, company_zh: str = "", ticker: str = "", days_back: int = 90, region: str = "KR"):
    collected = 0
    search_terms = expand_search_terms(company_en, company_zh, ticker)

    print(f"\nWill search {len(search_terms)} term variations:")
    for t in search_terms:
        print(f"  - {t}")

    seen_urls = set()

    for term in search_terms:
        print(f"\nSearching Naver Finance discussion for: {term}")
        threads = search_naver_finance(term)
        print(f"  Found {len(threads)} threads")

        for thread in threads:
            if thread["url"] in seen_urls:
                continue
            if not is_relevant(thread["title"], company_en, company_zh, ticker):
                continue
            seen_urls.add(thread["url"])
            print(f"  Thread: {thread['title'][:60]}")

            posts = get_discussion_posts(thread["url"])
            print(f"    Got {len(posts)} posts")

            for i, post in enumerate(posts):
                if not post["body"]:
                    continue
                supabase.table("posts").insert({
                    "source": "naver_finance",
                    "region": region,
                    "language": "ko",
                    "company": company_en,
                    "title": thread["title"] if i == 0 else None,
                    "body": post["body"],
                    "url": thread["url"],
                    "author": post["author"],
                    "posted_at": datetime.now(timezone.utc).isoformat(),
                    "source_weight": config.SOURCE_WEIGHTS["naver_finance"]
                }).execute()
                collected += 1

            time.sleep(1)

        print(f"\nSearching Naver News for: {term}")
        news_items = search_naver_news(term)
        relevant_news = [n for n in news_items if is_relevant(n["title"], company_en, company_zh, ticker)]
        print(f"  Found {len(relevant_news)} relevant news items")

        for item in relevant_news:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            print(f"  News: {item['title'][:60]}")

            supabase.table("posts").insert({
                "source": "naver_finance",
                "region": region,
                "language": "ko",
                "company": company_en,
                "title": item["title"],
                "body": item["body"],
                "url": item["url"],
                "author": item["author"],
                "posted_at": parse_pub_date(item["posted_at"]),
                "source_weight": config.SOURCE_WEIGHTS["naver_finance"]
            }).execute()
            collected += 1

        time.sleep(0.5)

    print(f"\nDone. Collected {collected} posts for '{company_en}'.")

if __name__ == "__main__":
    company_en = input("English name: ")
    company_zh = input("Local language name (press Enter to skip): ")
    ticker = input("Ticker / code (press Enter to skip): ")
    region = input("Region (HK/JP/KR/TW/US): ")
    collect_naver_finance(company_en, company_zh, ticker, region=region)