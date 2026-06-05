import requests
from bs4 import BeautifulSoup
from supabase import create_client
from datetime import datetime, timezone
import config
from urllib.parse import quote
import time

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-HK,zh-TW;q=0.9,zh;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://www.discuss.com.hk/',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'sec-ch-ua': '"Chromium";v="148", "Google Chrome";v="148"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
}

def scrape_discuss(company_en, company_zh, ticker, region="HK", days_back=30):
    posts = []
    session = requests.Session()
    
    # First visit homepage to get cookies
    try:
        session.get('https://www.discuss.com.hk/', headers=HEADERS, timeout=15)
        time.sleep(2)
    except:
        pass
    
    queries = [company_en]
    if company_zh:
        queries.append(company_zh)
    if ticker:
        queries.append(ticker)
    
    for query in queries:
        if not query:
            continue
        print(f"Searching Discuss.com.hk for: {query}")
        
        encoded = quote(query)
        search_url = f"https://www.discuss.com.hk/search.php?orderby=most_relevant&searchsubmit=yes&srcheng=1&srchtxt={encoded}"
        
        try:
            r = session.get(search_url, headers=HEADERS, timeout=15)
            print(f"  Status: {r.status_code}")
            
            if r.status_code != 200:
                continue
            
            soup = BeautifulSoup(r.text, 'html.parser')
            rows = soup.select('td.search-result-subject-box')
            print(f"  Found {len(rows)} results")
            
            for row in rows[:15]:
                try:
                    title_el = row.select_one('span.search-result-subject a')
                    preview_el = row.select_one('div.search-result-message a')
                    
                    title = title_el.get_text().strip() if title_el else ""
                    preview = preview_el.get_text().strip() if preview_el else ""
                    url = title_el.get('href', '') if title_el else ""
                    
                    if not title:
                        continue
                    
                    posts.append({
                        "source": "discuss",
                        "region": "HK",
                        "language": "zh",
                        "company": company_en,
                        "title": title,
                        "body": preview,
                        "url": url,
                        "author": "",
                        "posted_at": datetime.now(timezone.utc).isoformat(),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "source_weight": config.SOURCE_WEIGHTS.get("discuss", 0.9),
                        "sentiment_score": None,
                        "sentiment_label": None,
                        "keywords": [],
                        "relevance_tag": None,
                        "conviction": None,
                    })
                except:
                    continue
                    
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(2)
    
    print(f"Discuss collected {len(posts)} posts")
    if posts:
        supabase.table("posts").insert(posts).execute()
    return posts

if __name__ == "__main__":
    company_en = input("Company name (English): ")
    company_zh = input("Local name: ")
    ticker = input("Ticker: ")
    scrape_discuss(company_en, company_zh, ticker)