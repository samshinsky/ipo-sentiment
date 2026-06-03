from googleapiclient.discovery import build
from supabase import create_client
from datetime import datetime, timezone, timedelta
import config
import time

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

youtube = build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)

REGION_LANGUAGE = {
    "HK": ("HK", "zh-Hant"),
    "TW": ("TW", "zh-Hant"),
    "JP": ("JP", "ja"),
    "KR": ("KR", "ko"),
    "US": ("US", "en"),
}

def expand_search_terms(company_en, company_zh, ticker, region):
    terms = set()
    if company_en:
        terms.add(company_en + " IPO")
        terms.add(company_en.replace(" ", "") + " IPO")
        terms.add(company_en + " 上市")
        terms.add(company_en.replace(" ", "") + " 上市")
    if company_zh:
        terms.add(company_zh + " IPO")
        terms.add(company_zh + " 上市")
        terms.add(company_zh + " 新股")
    if ticker:
        terms.add(ticker + " IPO")
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

def search_videos(term, region_code, language, days_back=90):
    results = []
    published_after = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        res = youtube.search().list(
            q=term,
            part="snippet",
            type="video",
            maxResults=50,
            regionCode=region_code,
            relevanceLanguage=language,
            publishedAfter=published_after,
            order="date"
        ).execute()
        for item in res.get("items", []):
            results.append({
                "video_id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "channel": item["snippet"]["channelTitle"],
                "published_at": item["snippet"]["publishedAt"]
            })
    except Exception as e:
        print(f"  Error searching: {e}")
    return results

def get_comments(video_id, max_results=100):
    comments = []
    try:
        res = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=max_results,
            order="time",
            textFormat="plainText"
        ).execute()
        for item in res.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "body": top["textDisplay"],
                "author": top["authorDisplayName"],
                "published_at": top["publishedAt"],
                "likes": top["likeCount"]
            })
    except Exception as e:
        pass
    return comments

def collect_youtube(company_en: str, company_zh: str = "", ticker: str = "", days_back: int = 90, region: str = "HK"):
    collected = 0
    region_code, language = REGION_LANGUAGE.get(region, ("US", "en"))
    search_terms = expand_search_terms(company_en, company_zh, ticker, region)

    print(f"\nWill search {len(search_terms)} term variations:")
    for t in search_terms:
        print(f"  - {t}")

    seen_video_ids = set()

    for term in search_terms:
        print(f"\nSearching YouTube for: {term}")
        videos = search_videos(term, region_code, language, days_back)
        print(f"  Found {len(videos)} videos")

        for video in videos:
            if video["video_id"] in seen_video_ids:
                continue
            if not is_relevant(video["title"] + " " + video["description"], company_en, company_zh, ticker):
                print(f"  Skipping irrelevant: {video['title'][:50]}")
                continue

            seen_video_ids.add(video["video_id"])
            video_url = f"https://www.youtube.com/watch?v={video['video_id']}"
            print(f"  Video: {video['title'][:60]}")

            supabase.table("posts").insert({
                "source": "youtube",
                "region": region,
                "language": language,
                "company": company_en,
                "title": video["title"],
                "body": video["description"],
                "url": video_url,
                "author": video["channel"],
                "posted_at": video["published_at"],
                "source_weight": config.SOURCE_WEIGHTS["youtube"]
            }).execute()
            collected += 1

            comments = get_comments(video["video_id"])
            print(f"    Got {len(comments)} comments")

            for comment in comments:
                supabase.table("posts").insert({
                    "source": "youtube",
                    "region": region,
                    "language": language,
                    "company": company_en,
                    "title": None,
                    "body": comment["body"],
                    "url": video_url,
                    "author": comment["author"],
                    "posted_at": comment["published_at"],
                    "source_weight": config.SOURCE_WEIGHTS["youtube"] * 1.2
                }).execute()
                collected += 1

            time.sleep(0.5)

    print(f"\nDone. Collected {collected} posts for '{company_en}'.")

if __name__ == "__main__":
    company_en = input("English name: ")
    company_zh = input("Local language name (press Enter to skip): ")
    ticker = input("Ticker / code (press Enter to skip): ")
    region = input("Region (HK/JP/KR/TW/US): ")
    collect_youtube(company_en, company_zh, ticker, region=region)