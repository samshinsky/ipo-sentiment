import requests
from bs4 import BeautifulSoup
from supabase import create_client
from datetime import datetime, timezone
import config
import time

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://seekingalpha.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def expand_search_terms(company_en, ticker):
    terms = set()
    if company_en:
        terms.add(company_en)
        terms.add(company_en + " IPO")
        terms.add(company_en.replace(" ", ""))
    if ticker:
        terms.add(ticker)
        terms.add(ticker + " IPO")
    return list(terms)

def is_relevant(text, company_en, ticker):
    text_lower = text.lower()
    checks = []
    if company_en:
        checks.append(company_en.lower())
        checks.append(company_en.lower().replace(" ", ""))
    if ticker:
        checks.append(ticker.lower())
    return any(c in text_lower for c in checks)

def search_seeking_alpha(term):
    results = []
    url = f"https://seekingalpha.com/search?q={requests.utils.quote(term)}&tab=articles"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        print(f"  Status: {res.status_code}")
        if res.status_code != 200:
            return results
        soup = BeautifulSoup(res.text, "html.parser")
        for item in soup.select("article, div[data-test-id='post-list-item']"):
            title_el = item.select_one("a[data-test-id='post-list-item-title'], h3 a, h2 a")
            if not title_el:
                continue
            title = title_el.text.strip()
            href = title_el.get("href", "")
            if not href.startswith("http"):
                href = "https://seekingalpha.com" + href
            author_el = item.select_one("span[data-test-id='author-name'], a.author")
            date_el = item.select_one("time, span[data-test-id='post-date']")
            if title and len(title) > 3:
                results.append({
                    "url": href,
                    "title": title,
                    "author": author_el.text.strip() if author_el else "",
                    "date": date_el.get("datetime", "") if date_el else ""
                })
    except Exception as e:
        print(f"  Error: {e}")
    return results

def get_article_body(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return ""
        soup = BeautifulSoup(res.text, "html.parser")
        content = soup.select_one("div[data-test-id='article-content'], div.sa-art, section.paywall")
        if content:
            return content.get_text(separator="\n").strip()
        for div in soup.select("div.article-content, div#main-content"):
            text = div.get_text(separator="\n").strip()
            if len(text) > 100:
                return text
    except Exception as e:
        print(f"  Error fetching article: {e}")
    return ""

def collect_seeking_alpha(company_en: str, company_zh: str = "", ticker: str = "", days_back: int = 90, region: str = "HK"):
    collected = 0
    search_terms = expand_search_terms(company_en, ticker)

    print(f"\nWill search {len(search_terms)} term variations:")
    for t in search_terms:
        print(f"  - {t}")

    seen_urls = set()

    for term in search_terms:
        print(f"\nSearching Seeking Alpha for: {term}")
        articles = search_seeking_alpha(term)
        print(f"  Found {len(articles)} articles")

        for article in articles:
            if article["url"] in seen_urls:
                continue
            if not is_relevant(article["title"], company_en, ticker):
                print(f"  Skipping irrelevant: {article['title'][:50]}")
                continue

            seen_urls.add(article["url"])
            print(f"  Article: {article['title'][:60]}")

            body = get_article_body(article["url"])

            supabase.table("posts").insert({
                "source": "seeking_alpha",
                "region": region,
                "language": "en",
                "company": company_en,
                "title": article["title"],
                "body": body,
                "url": article["url"],
                "author": article["author"],
                "posted_at": article["date"] or datetime.now(timezone.utc).isoformat(),
                "source_weight": config.SOURCE_WEIGHTS["seeking_alpha"]
            }).execute()
            collected += 1
            time.sleep(1.5)

    print(f"\nDone. Collected {collected} posts for '{company_en}'.")

if __name__ == "__main__":
    company_en = input("English name: ")
    company_zh = input("Local language name (press Enter to skip): ")
    ticker = input("Ticker / code (press Enter to skip): ")
    region = input("Region (HK/JP/KR/TW/US): ")
    collect_seeking_alpha(company_en, company_zh, ticker, region=region)