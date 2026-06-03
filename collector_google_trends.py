from pytrends.request import TrendReq
from supabase import create_client
from datetime import datetime, timezone
import config
import time

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

REGION_GEO = {
    "HK": "HK",
    "TW": "TW",
    "JP": "JP",
    "KR": "KR",
    "US": "US",
    "CN": "CN",
}

def collect_google_trends(company_en: str, company_zh: str = "", ticker: str = "", days_back: int = 90, region: str = "HK"):
    collected = 0
    geo = REGION_GEO.get(region, "")
    
    search_terms = [t for t in [company_en, company_zh, ticker] if t]
    search_terms = search_terms[:5]

    print(f"\nFetching Google Trends for: {search_terms}")
    print(f"  Region: {geo}, Days back: {days_back}")

    pytrends = TrendReq(hl="zh-HK", tz=480)

    timeframe = f"today {days_back}-d" if days_back <= 90 else f"today {min(days_back, 270)}-d"

    try:
        pytrends.build_payload(
            search_terms[:5],
            cat=0,
            timeframe=timeframe,
            geo=geo,
            gprop=""
        )

        interest_over_time = pytrends.interest_over_time()

        if interest_over_time.empty:
            print("  No trend data found")
            return

        print(f"  Got {len(interest_over_time)} data points")

        for date, row in interest_over_time.iterrows():
            for term in search_terms:
                if term not in row:
                    continue
                value = int(row[term])
                if value == 0:
                    continue

                supabase.table("posts").insert({
                    "source": "google_trends",
                    "region": region,
                    "language": "en",
                    "company": company_en,
                    "title": f"Google Trends: {term}",
                    "body": f"Search interest score: {value}/100 for '{term}' in {geo}",
                    "url": f"https://trends.google.com/trends/explore?q={term}&geo={geo}",
                    "author": "google_trends",
                    "posted_at": date.isoformat(),
                    "source_weight": config.SOURCE_WEIGHTS["google_trends"]
                }).execute()
                collected += 1

        time.sleep(2)

        related_queries = pytrends.related_queries()
        for term in search_terms:
            if term not in related_queries:
                continue
            top = related_queries[term].get("top")
            if top is not None and not top.empty:
                print(f"  Related queries for '{term}':")
                for _, qrow in top.head(10).iterrows():
                    query = qrow.get("query", "")
                    value = qrow.get("value", 0)
                    if query:
                        print(f"    - {query} ({value})")
                        supabase.table("posts").insert({
                            "source": "google_trends",
                            "region": region,
                            "language": "en",
                            "company": company_en,
                            "title": f"Related search: {query}",
                            "body": f"Related query to '{term}' with interest score {value}",
                            "url": f"https://trends.google.com/trends/explore?q={term}&geo={geo}",
                            "author": "google_trends",
                            "posted_at": datetime.now(timezone.utc).isoformat(),
                            "source_weight": config.SOURCE_WEIGHTS["google_trends"]
                        }).execute()
                        collected += 1

    except Exception as e:
        print(f"  Error: {e}")

    print(f"\nDone. Collected {collected} trend data points for '{company_en}'.")

if __name__ == "__main__":
    company_en = input("English name: ")
    company_zh = input("Local language name (press Enter to skip): ")
    ticker = input("Ticker / code (press Enter to skip): ")
    region = input("Region (HK/JP/KR/TW/US): ")
    collect_google_trends(company_en, company_zh, ticker, region=region)