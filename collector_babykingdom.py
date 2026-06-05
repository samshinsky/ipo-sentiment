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
    'Referer': 'https://www.baby-kingdom.com/',
}

def scrape_babykingdom(company_en, company_zh, ticker, region="HK", days_back=30):
    posts = []
    session = requests.Session()
    
    try:
        session.get('https://www.baby-kingdom.com/', headers=HEADERS, timeout=15)
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
        print(f"Searching Baby Kingdom for: {query}")
        
        encoded = quote(query)
        search_url = f"https://www.baby-kingdom.com/search.php?mod=forum&srchtxt={encoded}&orderby=lastpost&ascdesc=desc&searchsubmit=yes&keyword={encoded}"
        
        try:
            r = session.get(search_url, headers=HEADERS, timeout=15)
            print(f"  Status: {r.status_code}")
            
            if r.status_code != 200:
                continue
            
            soup = BeautifulSoup(r.text, 'html.parser')
            items = soup.select('li.pbw')
            print(f"  Found {len(items)} results")
            
            for item in items[:20]:
                try:
                    title_el = item.select_one('h3.xs3 a')
                    if not title_el:
                        continue
                    
                    title = title_el.get_text().strip()
                    url = title_el.get('href', '')
                    
                    preview_el = item.select_one('p:nth-of-type(2)')
                    preview = preview_el.get_text().strip() if preview_el else title
                    
                    if not title or len(title) < 3:
                        continue
                    
                    posts.append({
                        "source": "babykingdom",
                        "region": "HK",
                        "language": "zh",
                        "company": company_en,
                        "title": title,
                        "body": preview[:500],
                        "url": url,
                        "author": "",
                        "posted_at": datetime.now(timezone.utc).isoformat(),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "source_weight": config.SOURCE_WEIGHTS.get("babykingdom", 0.8),
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
    
    print(f"Baby Kingdom collected {len(posts)} posts")
    if posts:
        supabase.table("posts").insert(posts).execute()
    return posts

if __name__ == "__main__":
    company_en = input("Company name (English): ")
    company_zh = input("Local name: ")
    ticker = input("Ticker: ")
    scrape_babykingdom(company_en, company_zh, ticker)