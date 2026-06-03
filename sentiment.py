from google import genai
from supabase import create_client
import config
import json
import math
import os

os.environ["HTTPS_PROXY"] = f"http://{config.BRIGHTDATA_USER}-country-us:{config.BRIGHTDATA_PASS}@{config.BRIGHTDATA_HOST}:{config.BRIGHTDATA_PORT}"
os.environ["HTTP_PROXY"] = f"http://{config.BRIGHTDATA_USER}-country-us:{config.BRIGHTDATA_PASS}@{config.BRIGHTDATA_HOST}:{config.BRIGHTDATA_PORT}"

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
client = genai.Client(api_key=config.GEMINI_API_KEY)

def score_batch(posts):
    if not posts:
        return []
    
    posts_text = ""
    for i, post in enumerate(posts):
        text = (post.get("body") or post.get("title") or "")[:500]
        lang = post.get("language", "en")
        source = post.get("source", "")
        posts_text += f"[{i}] lang={lang} source={source}\n{text}\n\n"
    
    prompt = f"""You are a financial sentiment analyst specializing in IPO retail investor sentiment across Asian markets.

Analyze each numbered post below and return a JSON array with one object per post containing:
- "index": the post number
- "sentiment": "bullish", "bearish", or "neutral"
- "score": confidence from -1.0 to 1.0 (negative for bearish e.g. -0.8, positive for bullish e.g. 0.8, 0.0 for neutral)
- "relevance": "ipo_related", "product_related", or "general_mention"
- "conviction": 0.0 to 1.0 — how strongly does this post express an opinion? (0 = vague mention, 1 = very strong opinion)

For relevance:
- ipo_related: mentions subscription, listing, share price, IPO, public offering, 上市, 新股, 打新, 상장, 公募, 上場
- product_related: mentions the company's product/service/brand but not the stock
- general_mention: just mentions the company name in passing

Posts to analyze:
{posts_text}

Return ONLY a valid JSON array, no other text."""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    response_text = response.text.strip()
    
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    
    return json.loads(response_text.strip())

def calculate_retail_score(data):
    if not data:
        return 0
    total_posts = len(data)
    volume_score = min(30, math.log1p(total_posts) * 5)
    weighted_sentiment = 0
    total_weight = 0
    for p in data:
        source_weight = float(p.get('source_weight') or 1.0)
        sentiment_score = float(p.get('sentiment_score') or 0)
        conviction = float(p.get('conviction') or 0.5)
        relevance = p.get('relevance_tag', 'general_mention')
        relevance_multiplier = 2.0 if relevance == 'ipo_related' else 1.0
        effective_weight = source_weight * conviction * relevance_multiplier
        weighted_sentiment += sentiment_score * effective_weight
        total_weight += effective_weight
    if total_weight > 0:
        avg_sentiment = weighted_sentiment / total_weight
        sentiment_component = (avg_sentiment + 1) / 2 * 70
    else:
        sentiment_component = 35
    return round(min(100, max(0, volume_score + sentiment_component)))

def run_sentiment(company_en, days_back=30):
    print(f"\nScoring sentiment for '{company_en}' (last {days_back} days)...")
    
    result = supabase.table("posts")\
        .select("id, body, title, language, source, source_weight")\
        .eq("company", company_en)\
        .is_("sentiment_label", "null")\
        .execute()
    
    posts = result.data
    print(f"Found {len(posts)} unscored posts")
    
    if not posts:
        print("Nothing to score — run a collection first.")
        return
    
    batch_size = 20
    scored = 0
    
    for i in range(0, len(posts), batch_size):
        batch = posts[i:i+batch_size]
        print(f"  Scoring batch {i//batch_size + 1} ({len(batch)} posts)...")
        try:
            results = score_batch(batch)
            for r in results:
                post = batch[r['index']]
                supabase.table("posts").update({
                    "sentiment_score": r['score'],
                    "sentiment_label": r['sentiment'],
                    "relevance_tag": r['relevance'],
                    "conviction": r.get('conviction', 0.5)
                }).eq("id", post["id"]).execute()
                scored += 1
        except Exception as e:
            print(f"  Batch error: {e}")
            continue
    
    print(f"Done. Scored {scored} posts.")
    print_summary(company_en)

def print_summary(company_en):
    summary = supabase.table("posts")\
        .select("sentiment_label, relevance_tag, source_weight, source, sentiment_score, conviction")\
        .eq("company", company_en)\
        .execute()
    
    data = summary.data
    if not data:
        return
    
    bullish = [p for p in data if p['sentiment_label'] == 'bullish']
    bearish = [p for p in data if p['sentiment_label'] == 'bearish']
    neutral = [p for p in data if p['sentiment_label'] == 'neutral']
    ipo_related = [p for p in data if p.get('relevance_tag') == 'ipo_related']
    total = len(data)
    retail_score = calculate_retail_score(data)
    
    print(f"\n{'='*50}")
    print(f"PAMALICAN ASSET MANAGEMENT")
    print(f"IPO Sentiment Report: {company_en}")
    print(f"{'='*50}")
    print(f"Retail Sentiment Score: {retail_score}/100")
    
    if retail_score >= 75:
        signal = "EXTREMELY FROTHY"
    elif retail_score >= 60:
        signal = "STRONGLY BULLISH"
    elif retail_score >= 50:
        signal = "MILDLY BULLISH"
    elif retail_score >= 40:
        signal = "NEUTRAL"
    elif retail_score >= 25:
        signal = "MILDLY BEARISH"
    else:
        signal = "COLD / NO INTEREST"
    
    print(f"Signal: {signal}")
    print(f"\nPost breakdown ({total} total):")
    print(f"  Bullish:      {len(bullish)} ({round(len(bullish)/total*100)}%)")
    print(f"  Bearish:      {len(bearish)} ({round(len(bearish)/total*100)}%)")
    print(f"  Neutral:      {len(neutral)} ({round(len(neutral)/total*100)}%)")
    print(f"  IPO-related:  {len(ipo_related)} ({round(len(ipo_related)/total*100)}%)")
    print(f"\nSources contributing:")
    sources = {}
    for p in data:
        s = p.get('source', 'unknown')
        sources[s] = sources.get(s, 0) + 1
    for source, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {source}: {count} posts")

if __name__ == "__main__":
    company_en = input("Company name: ")
    days = input("Days back (7/30/60/90, press Enter for 30): ").strip()
    days = int(days) if days else 30
    run_sentiment(company_en, days)