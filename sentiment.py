import anthropic
from supabase import create_client
import config
import json
import math

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

def score_batch(posts):
    if not posts:
        return []
    posts_text = ""
    for i, post in enumerate(posts):
        text = (post.get("body") or post.get("title") or "")[:500]
        lang = post.get("language", "en")
        source = post.get("source", "")
        posts_text += "[" + str(i) + "] lang=" + lang + " source=" + source + "\n" + text + "\n\n"
    prompt = """You are a financial sentiment analyst specializing in IPO retail investor sentiment across Asian markets.

Analyze each numbered post below and return a JSON array with one object per post containing:
- "index": the post number
- "sentiment": "bullish", "bearish", or "neutral"
- "score": confidence from -1.0 to 1.0 (negative for bearish e.g. -0.8, positive for bullish e.g. 0.8, 0.0 for neutral)
- "relevance": "ipo_related", "product_related", "general_mention", or "news_article"
- "conviction": 0.0 to 1.0 how strongly does this post express an opinion?

For relevance:
- ipo_related: mentions subscription, listing, share price, IPO, public offering, 上市, 新股, 打新, 상장, 公募, 上場
- product_related: mentions the company product/service/brand but not the stock
- general_mention: just mentions the company name in passing
- news_article: written by a journalist or media outlet reporting facts objectively — NOT expressing retail investor opinion. Signs include: formal tone, third-person reporting, quotes from executives/analysts, news source attribution, factual reporting without personal opinion

Posts to analyze:
""" + posts_text + """
Return ONLY a valid JSON array, no other text. Example: [{"index":0,"sentiment":"bullish","score":0.8,"relevance":"ipo_related","conviction":0.9}]"""
    messages = [{"role": "user", "content": prompt}]
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        messages=messages
    )
    response_text = message.content[0].text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    response_text = response_text.strip()
    parsed = json.loads(response_text)
    if isinstance(parsed, dict):
        parsed = [parsed]
    return parsed

def calculate_retail_score(data):
    if not data:
        return 0
    # Filter out news articles
    data = [p for p in data if p.get('relevance_tag') != 'news_article']
    if not data:
        return 0
    total_posts = len(data)
    volume_score = min(30, math.log1p(total_posts) * 5)
    weighted_sentiment = 0
    total_weight = 0
    for p in data:
        source_weight = float(p.get("source_weight") or 1.0)
        sentiment_score = float(p.get("sentiment_score") or 0)
        conviction = float(p.get("conviction") or 0.5)
        relevance = p.get("relevance_tag", "general_mention")
        relevance_multiplier = 2.0 if relevance == "ipo_related" else 1.0
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
    print("Scoring sentiment for " + company_en + "...")
    result = supabase.table("posts").select("id, body, title, language, source, source_weight").eq("company", company_en).is_("sentiment_label", "null").execute()
    posts = result.data
    print("Found " + str(len(posts)) + " unscored posts")
    if not posts:
        print("Nothing to score.")
        return
    batch_size = 20
    scored = 0
    for i in range(0, len(posts), batch_size):
        batch = posts[i:i+batch_size]
        print("  Scoring batch " + str(i//batch_size + 1) + " (" + str(len(batch)) + " posts)...")
        try:
            results = score_batch(batch)
            for r in results:
                if not isinstance(r, dict):
                    continue
                idx = r.get("index", 0)
                if idx >= len(batch):
                    continue
                post = batch[idx]
                supabase.table("posts").update({
                    "sentiment_score": r.get("score", 0),
                    "sentiment_label": r.get("sentiment", "neutral"),
                    "relevance_tag": r.get("relevance", "general_mention"),
                    "conviction": r.get("conviction", 0.5)
                }).eq("id", post["id"]).execute()
                scored += 1
        except Exception as e:
            print("  Batch error: " + str(e))
            continue
    print("Done. Scored " + str(scored) + " posts.")

def print_summary(company_en):
    summary = supabase.table("posts").select("sentiment_label, relevance_tag, source_weight, source, sentiment_score, conviction").eq("company", company_en).execute()
    data = summary.data
    if not data:
        return
    data = [p for p in data if p.get('relevance_tag') != 'news_article']
    bullish = [p for p in data if p["sentiment_label"] == "bullish"]
    bearish = [p for p in data if p["sentiment_label"] == "bearish"]
    neutral = [p for p in data if p["sentiment_label"] == "neutral"]
    ipo_related = [p for p in data if p.get("relevance_tag") == "ipo_related"]
    total = len(data)
    if total == 0:
        return
    retail_score = calculate_retail_score(data)
    print("="*50)
    print("PAMALICAN ASSET MANAGEMENT")
    print("IPO Sentiment Report: " + company_en)
    print("="*50)
    print("Retail Sentiment Score: " + str(retail_score) + "/100")
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
    print("Signal: " + signal)
    print("Bullish: " + str(len(bullish)) + " Bearish: " + str(len(bearish)) + " Neutral: " + str(len(neutral)) + " IPO-related: " + str(len(ipo_related)))

if __name__ == "__main__":
    company_en = input("Company name: ")
    days = input("Days back (press Enter for 30): ").strip()
    days = int(days) if days else 30
    run_sentiment(company_en, days)