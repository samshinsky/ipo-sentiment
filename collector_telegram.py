import asyncio
from telethon import TelegramClient
from supabase import create_client
from datetime import datetime, timezone
import config

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

async def collect_telegram(company_en: str, company_zh: str, stock_code: str, days_back: int = 90):
    client = TelegramClient('session', config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH)
    await client.start()

    cutoff = datetime.now(timezone.utc).timestamp() - (days_back * 86400)
    collected = 0
    search_terms = [t.lower() for t in [company_en, company_zh, stock_code] if t]

    for channel in config.TELEGRAM_CHANNELS:
        print(f"Scraping {channel}...")
        try:
            async for message in client.iter_messages(channel, limit=500):
                if not message.date:
                    continue
                if message.date.timestamp() < cutoff:
                    break
                if not message.text:
                    continue
                msg_lower = message.text.lower()
                if not any(term in msg_lower for term in search_terms):
                    continue

                supabase.table("posts").insert({
                    "source": "telegram",
                    "region": "HK",
                    "language": "zh",
                    "company": company_en,
                    "title": None,
                    "body": message.text,
                    "url": f"https://t.me/{channel}/{message.id}",
                    "author": str(message.sender_id),
                    "posted_at": message.date.isoformat(),
                    "source_weight": config.SOURCE_WEIGHTS["telegram"]
                }).execute()
                collected += 1
                print(f"  Found: {message.text[:80]}...")

        except Exception as e:
            print(f"Error on {channel}: {e}")

    await client.disconnect()
    print(f"Done. Collected {collected} posts for '{company_en}'.")

if __name__ == "__main__":
    company_en = input("English name: ")
    company_zh = input("Chinese name: ")
    stock_code = input("Stock code: ")
    asyncio.run(collect_telegram(company_en, company_zh, stock_code))