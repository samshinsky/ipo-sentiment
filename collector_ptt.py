import requests
from bs4 import BeautifulSoup
from supabase import create_client
from datetime import datetime, timezone
import config

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

BASE_URL = "https://www.ptt.cc"

SESSION = requests.Session()
SESSION.cookies.set("over18", "1")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.ptt.cc",
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

def search_board(term, board="Stock"):
    results = []
    url = f"{BASE_URL}/bbs/{board}/search?q={requests.utils.quote(term)}"
    try:
        res = SESSION.get(url, headers=HEADERS, timeout=10)
        print(f"  Status: {res.status_code}")
        if res.status_code != 200:
            return results
        soup = BeautifulSoup(res.text, "html.parser")
        for item in soup.select("div.r-ent"):
            title_el = item.select_one("div.title a")
            if not title_el:
                continue
            title = title_el.text.strip()
            link = BASE_URL + title_el["href"]
            results.append({"title": title, "url": link})
    except Exception as e:
        print(f"  Error searching: {e}")
    return results

def get_thread(url):
    posts = []
    try:
        res = SESSION.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return posts
        soup = BeautifulSoup(res.text, "html.parser")

        main_content = soup.select_one("div#main-content")
        if not main_content:
            return posts

        for tag in main_content.select("div.article-metaline, div.article-metaline-right"):
            tag.decompose()
        for span in main_content.select("span.f2"):
            span.decompose()

        text = main_content.get_text(separator="\n").strip()
        if text:
            posts.append({"body": text, "author": "", "type": "main"})

        for push in soup.select("div.push"):
            push_content = push.select_one("span.push-content")
            push_userid = push.select_one("span.push-userid")
            if push_content:
                posts.append({
                    "body": push_content.text.strip().lstrip(": "),
                    "author": push_userid.text.strip() if push_userid else "",
                    "type": "push"
                })
    except Exception as e:
        print(f"  Error fetching thread: {e}")
    return posts

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

def search_ptt(company_en: str, company_zh: str = "", ticker: str = "", days_back: int = 90, region: str = "TW"):
    collected = 0
    search_terms = expand_search_terms(company_en, company_zh, ticker)

    print(f"\nWill search {len(search_terms)} term variations:")
    for t in search_terms:
        print(f"  - {t}")

    seen_urls = set()
    boards = ["Stock", "Finance"]

    for board in boards:
        for term in search_terms:
            print(f"\nSearching PTT /{board}/ for: {term}")
            threads = search_board(term, board)
            print(f"  Found {len(threads)} threads")

            for thread in threads:
                if thread["url"] in seen_urls:
                    continue

                if not is_relevant(thread["title"], company_en, company_zh, ticker):
                    print(f"  Skipping irrelevant: {thread['title'][:50]}")
                    continue

                seen_urls.add(thread["url"])
                print(f"  Thread: {thread['title'][:60]}")
                posts = get_thread(thread["url"])
                print(f"    Got {len(posts)} posts/pushes")

                for i, post in enumerate(posts):
                    if not post["body"]:
                        continue
                    supabase.table("posts").insert({
                        "source": "ptt",
                        "region": region,
                        "language": "zh",
                        "company": company_en,
                        "title": thread["title"] if i == 0 else None,
                        "body": post["body"],
                        "url": thread["url"],
                        "author": post["author"],
                        "posted_at": datetime.now(timezone.utc).isoformat(),
                        "source_weight": config.SOURCE_WEIGHTS["ptt"]
                    }).execute()
                    collected += 1

    print(f"\nDone. Collected {collected} posts for '{company_en}'.")

if __name__ == "__main__":
    company_en = input("English name: ")
    company_zh = input("Local language name (press Enter to skip): ")
    ticker = input("Ticker / code (press Enter to skip): ")
    region = input("Region (HK/JP/KR/TW/US): ")
    search_ptt(company_en, company_zh, ticker, region=region)