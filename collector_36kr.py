import requests
from bs4 import BeautifulSoup
from supabase import create_client
from datetime import datetime, timezone
import config
import time

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://36kr.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

def expand_search_terms(company_en, company_zh, ticker):
    terms = set()
    if company_en:
        terms.add(company_en)
        terms.add(company_en.replace(" ", ""))
    if company_zh:
        terms.add(company_zh)
        terms.add(company_zh + "IPO")
        terms.add(company_zh + "上市")
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

def search_36kr(term):
    results = []
    url = f"https://36kr.com/search/articles/{requests.utils.quote(term)}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        print(f"  Status: {res.status_code}")
        if res.status_code != 200:
            return results
        soup = BeautifulSoup(res.text, "html.parser")
        for item in soup.select("div.article-item, div.flow-item, a.article-card"):
            title_el = item.select_one("a.title, h3, h2, div.title")
            if not title_el:
                continue
            title = title_el.text.strip()
            href = title_el.get("href") or item.select_one("a[href]")
            if hasattr(href, "get"):
                href = href.get("href", "")
            if not href:
                continue
            if not href.startswith("http"):
                href = "https://36kr.com" + href
            if title and len(title) > 3:
                results.append({"url": href, "title": title})
    except Exception as e:
        print(f"  Error: {e}")
    return results

def get_article(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return ""
        soup = BeautifulSoup(res.text, "html.parser")
        content = soup.select_one("div.common-width, div.article-content, div#article-content")
        if content:
            return content.get_text(separator="\n").strip()
    except Exception as e:
        print(f"  Error fetching article: {e}")
    return ""

def collect_36kr(company_en: str, company_zh: str = "", ticker: str = "", days_back: int = 90, region: str = "HK"):
    collected = 0
    search_terms = expand_search_terms(company_en, company_zh, ticker)

    print(f"\nWill search {len(search_terms)} term variations:")
    for t in search_terms:
        print(f"  - {t}")

    seen_urls = set()

    for term in search_terms:
        print(f"\nSearching 36Kr for: {term}")
        articles = search_36kr(term)
        print(f"  Found {len(articles)} articles")

        for article in articles:
            if article["url"] in seen_urls:
                continue
            if not is_relevant(article["title"], company_en, company_zh, ticker):
                print(f"  Skipping irrelevant: {article['title'][:50]}")
                continue

            seen_urls.add(article["url"])
            print(f"  Article: {article['title'][:60]}")

            body = get_article(article["url"])

            supabase.table("posts").insert({
                "source": "36kr",
                "region": region,
                "language": "zh",
                "company": company_en,
                "title": article["title"],
                "body": body,
                "url": article["url"],
                "author": "",
                "posted_at": datetime.now(timezone.utc).isoformat(),
                "source_weight": config.SOURCE_WEIGHTS["36kr"]
            }).execute()
            collected += 1
            time.sleep(1)

    print(f"\nDone. Collected {collected} posts for '{company_en}'.")

if __name__ == "__main__":
    company_en = input("English name: ")
    company_zh = input("Local language name (press Enter to skip): ")
    ticker = input("Ticker / code (press Enter to skip): ")
    region = input("Region (HK/JP/KR/TW/US): ")
    collect_36kr(company_en, company_zh, ticker, region=region)