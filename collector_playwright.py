import asyncio
from playwright.async_api import async_playwright
from supabase import create_client
from datetime import datetime, timezone
import config
import re

supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

def proxy_for_country(country_code):
    return {
        "server": f"http://{config.BRIGHTDATA_HOST}:{config.BRIGHTDATA_PORT}",
        "username": f"{config.BRIGHTDATA_USER}-country-{country_code.lower()}",
        "password": config.BRIGHTDATA_PASS,
    }

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    return text if len(text) > 5 else ""

def is_relevant(text, company_en, company_zh, ticker):
    if not text:
        return False
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

async def save_post(source, region, language, company_en, title, body, url, author, weight, posted_at=None):
    body = clean_text(body)
    if not body:
        return
    supabase.table("posts").insert({
        "source": source,
        "region": region,
        "language": language,
        "company": company_en,
        "title": clean_text(title) if title else None,
        "body": body,
        "url": url,
        "author": author or "",
        "posted_at": posted_at or datetime.now(timezone.utc).isoformat(),
        "source_weight": weight
    }).execute()

async def scrape_dcard(page, company_en, company_zh, ticker, region):
    collected = 0
    print("\n[Dcard]")
    search_terms = [t for t in [company_en, company_zh, ticker] if t]
    seen_ids = set()
    for term in search_terms:
        try:
            await page.goto(f"https://www.dcard.tw/search?query={term}&tab=post", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            posts = await page.evaluate("""() => {
                const items = document.querySelectorAll('article, div[class*="PostEntry"]');
                return Array.from(items).map(el => ({
                    title: el.querySelector('h2, h3, [class*="title"]')?.innerText?.trim() || '',
                    url: el.querySelector('a')?.href || '',
                    excerpt: el.querySelector('p, [class*="excerpt"], [class*="content"]')?.innerText?.trim() || ''
                })).filter(p => p.title && p.url);
            }""")
            print(f"  [{term}] Found {len(posts)} posts")
            for post in posts:
                post_id = post['url'].split('/')[-1]
                if post_id in seen_ids:
                    continue
                if not is_relevant(post['title'] + ' ' + post['excerpt'], company_en, company_zh, ticker):
                    continue
                seen_ids.add(post_id)
                await save_post("dcard", region, "zh", company_en, post['title'], post['excerpt'], post['url'], "", config.SOURCE_WEIGHTS["dcard"])
                collected += 1
                try:
                    await page.goto(post['url'], wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2)
                    comments = await page.evaluate("""() => {
                        const els = document.querySelectorAll('[class*="Comment"], [class*="comment"]');
                        return Array.from(els).map(el => ({
                            body: el.innerText?.trim() || '',
                            author: el.querySelector('[class*="author"], [class*="name"]')?.innerText?.trim() || ''
                        })).filter(c => c.body.length > 5);
                    }""")
                    for comment in comments:
                        await save_post("dcard", region, "zh", company_en, None, comment['body'], post['url'], comment['author'], config.SOURCE_WEIGHTS["dcard"])
                        collected += 1
                except:
                    pass
                await asyncio.sleep(1)
        except Exception as e:
            print(f"  Error: {e}")
    print(f"  Collected {collected} posts")
    return collected

async def scrape_aastocks(page, company_en, company_zh, ticker, region):
    collected = 0
    print("\n[AAStocks]")
    search_terms = [t for t in [company_en, company_zh, ticker] if t]
    seen_urls = set()
    for term in search_terms:
        try:
            await page.goto(f"https://www.aastocks.com/tc/stocks/analysis/stock-aafn/0/all/1?search={term}", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            posts = await page.evaluate("""() => {
                const items = document.querySelectorAll('div.newsitem, div.news-item, li.news');
                return Array.from(items).map(el => ({
                    title: el.querySelector('a')?.innerText?.trim() || '',
                    url: el.querySelector('a')?.href || '',
                    body: el.innerText?.trim() || ''
                })).filter(p => p.title && p.url);
            }""")
            print(f"  [{term}] Found {len(posts)} posts")
            for post in posts:
                if post['url'] in seen_urls:
                    continue
                if not is_relevant(post['title'], company_en, company_zh, ticker):
                    continue
                seen_urls.add(post['url'])
                await save_post("aastocks", region, "zh", company_en, post['title'], post['body'], post['url'], "", config.SOURCE_WEIGHTS["aastocks"])
                collected += 1
        except Exception as e:
            print(f"  Error: {e}")
    print(f"  Collected {collected} posts")
    return collected

async def scrape_eastmoney(page, company_en, company_zh, ticker, region):
    collected = 0
    print("\n[Eastmoney]")
    search_terms = [t for t in [company_zh, company_en, ticker] if t]
    seen_urls = set()
    for term in search_terms:
        try:
            await page.goto(f"https://so.eastmoney.com/web/s?keyword={term}", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(4)
            articles = await page.evaluate("""() => {
                const items = document.querySelectorAll('div.news-item, div.item, li.item, div[class*="news"]');
                const results = [];
                items.forEach(el => {
                    const a = el.querySelector('a[href*="eastmoney"], a[href*="finance"]');
                    const title = a?.innerText?.trim() || el.querySelector('h3, h2, .title')?.innerText?.trim() || '';
                    const url = a?.href || '';
                    const body = el.innerText?.trim() || '';
                    if (title && url) results.push({title, url, body});
                });
                return results;
            }""")
            if not articles:
                articles = await page.evaluate("""() => {
                    const links = document.querySelectorAll('a[href*="finance.eastmoney"], a[href*="guba.eastmoney"]');
                    return Array.from(links).map(a => ({
                        title: a.innerText?.trim() || '',
                        url: a.href,
                        body: a.closest('div, li')?.innerText?.trim() || ''
                    })).filter(a => a.title.length > 5);
                }""")
            print(f"  [{term}] Found {len(articles)} articles")
            for article in articles:
                if article['url'] in seen_urls:
                    continue
                if not is_relevant(article['title'] + ' ' + article['body'], company_en, company_zh, ticker):
                    continue
                seen_urls.add(article['url'])
                await save_post("eastmoney", region, "zh", company_en, article['title'], article['body'], article['url'], "", config.SOURCE_WEIGHTS["eastmoney"])
                collected += 1
        except Exception as e:
            print(f"  Error: {e}")
    print(f"  Collected {collected} posts")
    return collected

async def scrape_xiaohongshu(page, company_en, company_zh, ticker, region):
    collected = 0
    print("\n[Xiaohongshu]")
    search_terms = [t for t in [company_zh, company_en, ticker] if t]
    seen_urls = set()
    for term in search_terms:
        try:
            await page.goto(f"https://www.xiaohongshu.com/search_result?keyword={term}&type=51", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(4)
            posts = await page.evaluate("""() => {
                const items = document.querySelectorAll('section.note-item, div[class*="note-item"]');
                return Array.from(items).map(el => ({
                    title: el.querySelector('a.title, span.title, [class*="title"]')?.innerText?.trim() || '',
                    url: el.querySelector('a')?.href || '',
                    body: el.querySelector('p, [class*="desc"]')?.innerText?.trim() || ''
                })).filter(p => p.url);
            }""")
            print(f"  [{term}] Found {len(posts)} posts")
            for post in posts:
                if post['url'] in seen_urls:
                    continue
                if not is_relevant(post['title'] + ' ' + post['body'], company_en, company_zh, ticker):
                    continue
                seen_urls.add(post['url'])
                await save_post("xiaohongshu", region, "zh", company_en, post['title'], post['body'], post['url'], "", config.SOURCE_WEIGHTS["xiaohongshu"])
                collected += 1
            await asyncio.sleep(2)
        except Exception as e:
            print(f"  Error: {e}")
    print(f"  Collected {collected} posts")
    return collected

async def scrape_yahoo_japan(page, company_en, company_zh, ticker, region):
    collected = 0
    print("\n[Yahoo Finance Japan]")
    yahoo_tickers = []
    if ticker:
        yahoo_tickers.append(f"{ticker}.T")
    else:
        search_terms = [t for t in [company_zh, company_en] if t]
        for term in search_terms:
            try:
                await page.goto(f"https://finance.yahoo.co.jp/search/?query={term}", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
                tickers = await page.evaluate("""() => {
                    const links = document.querySelectorAll('a[href*="/quote/"]');
                    const found = [];
                    links.forEach(a => {
                        const match = a.href.match(/quote\/([^/]+)/);
                        if (match && match[1].includes('.') && !found.includes(match[1])) {
                            found.push(match[1]);
                        }
                    });
                    return found.slice(0, 2);
                }""")
                for t in tickers:
                    if t not in yahoo_tickers:
                        yahoo_tickers.append(t)
            except Exception as e:
                print(f"  Error searching: {e}")
    print(f"  Will scrape forums for: {yahoo_tickers}")
    for yt in yahoo_tickers:
        forum_url = f"https://finance.yahoo.co.jp/quote/{yt}/forum"
        try:
            await page.goto(forum_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            posts = await page.evaluate("""() => {
                const items = document.querySelectorAll('li[class*="_InfiniteBbsList__item"]');
                return Array.from(items).map(el => ({
                    body: el.querySelector('p')?.innerText?.trim() || el.querySelector('[class*="_BbsItem__body"]')?.innerText?.trim() || '',
                    author: el.querySelector('[class*="_BbsItem__header"] span')?.innerText?.trim() || ''
                })).filter(p => p.body.length > 5);
            }""")
            print(f"  [{yt}] Found {len(posts)} posts")
            for i, post in enumerate(posts):
                await save_post("yahoo_japan", region, "ja", company_en,
                    company_en if i == 0 else None,
                    post['body'], forum_url, post['author'],
                    config.SOURCE_WEIGHTS["yahoo_japan"])
                collected += 1
        except Exception as e:
            print(f"  Error on {yt}: {e}")
    print(f"  Collected {collected} posts")
    return collected

async def scrape_minkabu(page, company_en, company_zh, ticker, region):
    collected = 0
    print("\n[Minkabu]")
    if not ticker:
        print("  No ticker provided — skipping Minkabu")
        return 0
    try:
        pick_url = f"https://minkabu.jp/stock/{ticker}/pick"
        await page.goto(pick_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        picks = await page.evaluate("""() => {
            const items = document.querySelectorAll('ul.border-t li');
            return Array.from(items).map(el => ({
                signal: el.querySelector('[class*="PicksBuy"], [class*="PicksSell"]')?.innerText?.trim() || '',
                body: el.innerText?.trim() || '',
                author: el.querySelector('div.w-full span')?.innerText?.trim() || ''
            })).filter(p => p.body.length > 3);
        }""")
        print(f"  Found {len(picks)} predictions")
        for pick in picks:
            await save_post("minkabu", region, "ja", company_en,
                f"Minkabu prediction: {pick['signal']}",
                pick['body'], pick_url, pick['author'],
                config.SOURCE_WEIGHTS["minkabu"])
            collected += 1
        analysis_url = f"https://minkabu.jp/stock/{ticker}/analysis"
        await page.goto(analysis_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        analysis = await page.evaluate("""() => {
            return document.querySelector('div#main')?.innerText?.trim() || '';
        }""")
        if analysis:
            await save_post("minkabu", region, "ja", company_en,
                "Minkabu analysis", analysis, analysis_url, "",
                config.SOURCE_WEIGHTS["minkabu"])
            collected += 1
    except Exception as e:
        print(f"  Error: {e}")
    print(f"  Collected {collected} posts")
    return collected

async def scrape_cafestock(page, company_en, company_zh, ticker, region):
    collected = 0
    print("\n[Cafe Stock]")
    search_terms = [t for t in [company_zh, company_en, ticker] if t]
    seen_urls = set()
    for term in search_terms:
        try:
            await page.goto(f"https://cafe.naver.com/ArticleSearchList.nhn?search.clubid=20537338&search.searchdate=all&search.query={term}", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            threads = await page.evaluate("""() => {
                const items = document.querySelectorAll('li.article-item, div.article-item, a.article-title, div.article-info');
                return Array.from(items).map(el => ({
                    title: el.querySelector('a, span.title, strong')?.innerText?.trim() || el.innerText?.trim() || '',
                    url: el.querySelector('a')?.href || el.href || ''
                })).filter(t => t.title && t.url && t.title.length > 3);
            }""")
            print(f"  [{term}] Found {len(threads)} threads")
            for thread in threads:
                if thread['url'] in seen_urls:
                    continue
                if not is_relevant(thread['title'], company_en, company_zh, ticker):
                    continue
                seen_urls.add(thread['url'])
                await save_post("cafestock", region, "ko", company_en, thread['title'], "", thread['url'], "", config.SOURCE_WEIGHTS["cafestock"])
                collected += 1
        except Exception as e:
            print(f"  Error: {e}")
    print(f"  Collected {collected} posts")
    return collected

async def scrape_stockfeel(page, company_en, company_zh, ticker, region):
    collected = 0
    print("\n[StockFeel]")
    search_terms = [t for t in [company_zh, company_en, ticker] if t]
    seen_urls = set()
    for term in search_terms:
        try:
            await page.goto(f"https://www.stockfeel.com.tw/isearch/?query={term}", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            posts = await page.evaluate("""() => {
                const items = document.querySelectorAll('a.result-item');
                return Array.from(items).map(el => ({
                    title: el.querySelector('div.result-title')?.innerText?.trim() || '',
                    url: el.href || '',
                    body: el.querySelector('div.result-content')?.innerText?.trim() || ''
                })).filter(p => p.title && p.url);
            }""")
            print(f"  [{term}] Found {len(posts)} posts")
            for post in posts:
                if post['url'] in seen_urls:
                    continue
                if not is_relevant(post['title'], company_en, company_zh, ticker):
                    continue
                seen_urls.add(post['url'])
                await save_post("stockfeel", region, "zh", company_en, post['title'], post['body'], post['url'], "", config.SOURCE_WEIGHTS["stockfeel"])
                collected += 1
        except Exception as e:
            print(f"  Error: {e}")
    print(f"  Collected {collected} posts")
    return collected

async def scrape_mobile01(page, company_en, company_zh, ticker, region):
    collected = 0
    print("\n[Mobile01]")
    search_terms = [t for t in [company_zh, company_en, ticker] if t]
    seen_titles = set()
    for term in search_terms:
        try:
            await page.goto(f"https://www.mobile01.com/googlesearch.php?query={term}", wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_selector('div.gsc-webResult.gsc-result', timeout=10000)
            except:
                print(f"  [{term}] No results loaded")
                continue
            await asyncio.sleep(2)
            threads = await page.evaluate("""() => {
                const items = document.querySelectorAll('div.gsc-webResult.gsc-result');
                const results = [];
                items.forEach(el => {
                    const title = el.querySelector('a.gs-title')?.innerText?.trim() || '';
                    const snippet = el.querySelector('.gs-snippet')?.innerText?.trim() || '';
                    if (title && snippet) results.push({title, body: snippet});
                });
                return results;
            }""")
            print(f"  [{term}] Found {len(threads)} threads")
            for thread in threads:
                if thread['title'] in seen_titles:
                    continue
                if not is_relevant(thread['title'] + ' ' + thread['body'], company_en, company_zh, ticker):
                    continue
                seen_titles.add(thread['title'])
                await save_post("mobile01", region, "zh", company_en,
                    thread['title'], thread['body'],
                    f"https://www.mobile01.com/googlesearch.php?query={term}",
                    "", config.SOURCE_WEIGHTS["mobile01"])
                collected += 1
        except Exception as e:
            print(f"  Error: {e}")
    print(f"  Collected {collected} posts")
    return collected

async def scrape_5ch(page, company_en, company_zh, ticker, region):
    collected = 0
    print("\n[5ch]")
    search_terms = [t for t in [company_zh, company_en, ticker] if t]
    seen_urls = set()
    for term in search_terms:
        try:
            await page.goto(f"https://find.5ch.net/search?q={term}", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            threads = await page.evaluate("""() => {
                const links = document.querySelectorAll('a[href*="5ch.net/test/read"]');
                return Array.from(links).map(a => ({
                    title: a.innerText?.trim() || '',
                    url: a.href
                })).filter(t => t.title.length > 3);
            }""")
            print(f"  [{term}] Found {len(threads)} threads")
            for thread in threads:
                if thread['url'] in seen_urls:
                    continue
                if not is_relevant(thread['title'], company_en, company_zh, ticker):
                    continue
                seen_urls.add(thread['url'])
                try:
                    await page.goto(thread['url'], wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2)
                    posts = await page.evaluate("""() => {
                        const items = document.querySelectorAll('div.post, article.post, div[class*="post"]');
                        return Array.from(items).map(el => ({
                            body: el.querySelector('div.message, div[class*="message"]')?.innerText?.trim() || el.innerText?.trim() || '',
                            author: el.querySelector('span.name, b')?.innerText?.trim() || ''
                        })).filter(p => p.body.length > 5);
                    }""")
                    for i, post in enumerate(posts):
                        await save_post("5ch", region, "ja", company_en,
                            thread['title'] if i == 0 else None,
                            post['body'], thread['url'], post['author'],
                            config.SOURCE_WEIGHTS["5ch"])
                        collected += 1
                    await asyncio.sleep(1)
                except:
                    pass
        except Exception as e:
            print(f"  Error: {e}")
    print(f"  Collected {collected} posts")
    return collected

async def scrape_jisilu(page, company_en, company_zh, ticker, region):
    collected = 0
    print("\n[Jisilu]")
    search_terms = [t for t in [company_zh, company_en, ticker] if t]
    seen_urls = set()
    for term in search_terms:
        try:
            await page.goto(f"https://www.jisilu.cn/search/result/?wd={term}", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            threads = await page.evaluate("""() => {
                const items = document.querySelectorAll('div.q-title a, h3.question-title a, a.question-link');
                return Array.from(items).map(a => ({
                    title: a.innerText?.trim() || '',
                    url: a.href
                })).filter(t => t.title.length > 3);
            }""")
            print(f"  [{term}] Found {len(threads)} threads")
            for thread in threads:
                if thread['url'] in seen_urls:
                    continue
                if not is_relevant(thread['title'], company_en, company_zh, ticker):
                    continue
                seen_urls.add(thread['url'])
                try:
                    await page.goto(thread['url'], wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2)
                    posts = await page.evaluate("""() => {
                        const items = document.querySelectorAll('div.answer-content, div.content, div.wiki-content');
                        return Array.from(items).map(el => ({
                            body: el.innerText?.trim() || '',
                            author: el.closest('[class*="item"]')?.querySelector('a.username, span.username')?.innerText?.trim() || ''
                        })).filter(p => p.body.length > 5);
                    }""")
                    for i, post in enumerate(posts):
                        await save_post("jisilu", region, "zh", company_en,
                            thread['title'] if i == 0 else None,
                            post['body'], thread['url'], post['author'],
                            config.SOURCE_WEIGHTS["jisilu"])
                        collected += 1
                    await asyncio.sleep(1)
                except:
                    pass
        except Exception as e:
            print(f"  Error: {e}")
    print(f"  Collected {collected} posts")
    return collected

async def scrape_36kr(page, company_en, company_zh, ticker, region):
    collected = 0
    print("\n[36Kr]")
    search_terms = [t for t in [company_zh, company_en, ticker] if t]
    seen_urls = set()
    for term in search_terms:
        try:
            await page.goto(f"https://36kr.com/search/articles/{term}", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(8)
            articles = await page.evaluate("""() => {
                const results = [];
                const items = document.querySelectorAll('li.search-result-list-item-article');
                items.forEach(el => {
                    const titleEl = el.querySelector('a.article-item-title');
                    const bodyEl = el.querySelector('a.article-item-description');
                    const title = titleEl?.innerText?.trim() || '';
                    const url = titleEl?.href || '';
                    const body = bodyEl?.innerText?.trim() || '';
                    if (title && url) results.push({title, url, body});
                });
                return results;
            }""")
            print(f"  [{term}] Found {len(articles)} articles")
            for article in articles:
                if article['url'] in seen_urls:
                    continue
                if not is_relevant(article['title'], company_en, company_zh, ticker):
                    continue
                seen_urls.add(article['url'])
                await save_post("36kr", region, "zh", company_en, article['title'], article['body'], article['url'], "", config.SOURCE_WEIGHTS["36kr"])
                collected += 1
        except Exception as e:
            print(f"  Error: {e}")
    print(f"  Collected {collected} posts")
    return collected

async def scrape_bilibili(page, company_en, company_zh, ticker, region):
    collected = 0
    print("\n[Bilibili]")
    search_terms = [t for t in [company_zh, company_en, ticker] if t]
    seen_urls = set()
    for term in search_terms:
        try:
            await page.goto(f"https://search.bilibili.com/all?keyword={term}&search_source=5", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            videos = await page.evaluate("""() => {
                const items = document.querySelectorAll('div.bili-video-card, div.video-item');
                return Array.from(items).map(el => ({
                    title: el.querySelector('h3, p.title, span.title')?.innerText?.trim() || '',
                    url: el.querySelector('a')?.href || '',
                    author: el.querySelector('span.up-name, a.up-name')?.innerText?.trim() || ''
                })).filter(v => v.title && v.url);
            }""")
            print(f"  [{term}] Found {len(videos)} videos")
            for video in videos:
                if video['url'] in seen_urls:
                    continue
                if not is_relevant(video['title'], company_en, company_zh, ticker):
                    continue
                seen_urls.add(video['url'])
                await save_post("bilibili", region, "zh", company_en, video['title'], "", video['url'], video['author'], config.SOURCE_WEIGHTS["bilibili"])
                collected += 1
        except Exception as e:
            print(f"  Error: {e}")
    print(f"  Collected {collected} posts")
    return collected

async def scrape_tonghuashun(page, company_en, company_zh, ticker, region):
    collected = 0
    print("\n[Tonghuashun]")
    search_terms = [t for t in [company_zh, company_en, ticker] if t]
    seen_urls = set()
    for term in search_terms:
        try:
            await page.goto(f"https://t.10jqka.com.cn/search?keyword={term}", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(4)
            threads = await page.evaluate("""() => {
                const items = document.querySelectorAll('div.list-item, li.item, div.articleitem, div.content-item');
                return Array.from(items).map(el => ({
                    title: el.querySelector('a.title, h3 a, h2 a, a')?.innerText?.trim() || '',
                    url: el.querySelector('a.title, h3 a, h2 a, a')?.href || ''
                })).filter(t => t.title && t.url && t.title.length > 3);
            }""")
            print(f"  [{term}] Found {len(threads)} threads")
            for thread in threads:
                if thread['url'] in seen_urls:
                    continue
                if not is_relevant(thread['title'], company_en, company_zh, ticker):
                    continue
                seen_urls.add(thread['url'])
                try:
                    await page.goto(thread['url'], wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2)
                    posts = await page.evaluate("""() => {
                        const items = document.querySelectorAll('div.reply-item, div.content, p.text');
                        return Array.from(items).map(el => ({
                            body: el.innerText?.trim() || '',
                            author: el.querySelector('span.name, a.name')?.innerText?.trim() || ''
                        })).filter(p => p.body.length > 5);
                    }""")
                    for i, post in enumerate(posts):
                        await save_post("tonghuashun", region, "zh", company_en,
                            thread['title'] if i == 0 else None,
                            post['body'], thread['url'], post['author'],
                            config.SOURCE_WEIGHTS["tonghuashun"])
                        collected += 1
                    await asyncio.sleep(1)
                except:
                    pass
        except Exception as e:
            print(f"  Error: {e}")
    print(f"  Collected {collected} posts")
    return collected

async def scrape_google_trends(page, company_en, company_zh, ticker, region):
    collected = 0
    print("\n[Google Trends]")
    search_terms = [t for t in [company_en, company_zh, ticker] if t][:3]
    for term in search_terms:
        try:
            geo = region if region in ["HK", "TW", "JP", "KR", "US"] else "HK"
            url = f"https://trends.google.com/trends/explore?q={term}&geo={geo}"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)
            trend_data = await page.evaluate("""() => {
                const values = document.querySelectorAll('text[class*="label"], div[class*="value"]');
                return Array.from(values).map(el => el.innerText?.trim()).filter(t => t && t.length > 0);
            }""")
            if trend_data:
                await save_post("google_trends", region, "en", company_en,
                    f"Google Trends: {term}",
                    f"Search interest data for '{term}' in {geo}: " + " | ".join(trend_data[:20]),
                    url, "google_trends",
                    config.SOURCE_WEIGHTS["google_trends"])
                collected += 1
            await asyncio.sleep(2)
        except Exception as e:
            print(f"  Error: {e}")
    print(f"  Collected {collected} data points")
    return collected

PROXY_SOURCES = {"dcard", "aastocks", "xiaohongshu", "jisilu", "tonghuashun", "cafestock"}

SOURCE_COUNTRY = {
    "dcard": "tw",
    "aastocks": "hk",
    "xiaohongshu": "hk",
    "jisilu": "cn",
    "tonghuashun": "cn",
    "cafestock": "kr",
}

SCRAPERS = {
    "dcard": scrape_dcard,
    "aastocks": scrape_aastocks,
    "eastmoney": scrape_eastmoney,
    "xiaohongshu": scrape_xiaohongshu,
    "yahoo_japan": scrape_yahoo_japan,
    "minkabu": scrape_minkabu,
    "cafestock": scrape_cafestock,
    "stockfeel": scrape_stockfeel,
    "mobile01": scrape_mobile01,
    "5ch": scrape_5ch,
    "jisilu": scrape_jisilu,
    "36kr": scrape_36kr,
    "bilibili": scrape_bilibili,
    "tonghuashun": scrape_tonghuashun,
    "google_trends": scrape_google_trends,
}

async def run_all(company_en, company_zh, ticker, region, sources=None):
    total = 0
    to_run = sources or list(SCRAPERS.keys())

    proxy_sources = [s for s in to_run if s in PROXY_SOURCES]
    normal_sources = [s for s in to_run if s not in PROXY_SOURCES]

    async with async_playwright() as p:
        if normal_sources:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                locale="zh-HK",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            for source in normal_sources:
                if source not in SCRAPERS:
                    print(f"Unknown source: {source}")
                    continue
                try:
                    count = await SCRAPERS[source](page, company_en, company_zh, ticker, region)
                    total += count
                except Exception as e:
                    print(f"Error in {source}: {e}")
            await browser.close()

        if proxy_sources:
            by_country = {}
            for source in proxy_sources:
                country = SOURCE_COUNTRY.get(source, "hk")
                by_country.setdefault(country, []).append(source)

            for country, sources_for_country in by_country.items():
                print(f"\n--- Using proxy with country: {country.upper()} ---")
                browser = await p.chromium.launch(
                    headless=True,
                    args=[f'--proxy-server=http://{config.BRIGHTDATA_HOST}:{config.BRIGHTDATA_PORT}']
                )
                context = await browser.new_context(
                    locale="zh-HK",
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    ignore_https_errors=True,
                    http_credentials={
                        "username": f"{config.BRIGHTDATA_USER}-country-{country}",
                        "password": config.BRIGHTDATA_PASS
                    }
                )
                page = await context.new_page()
                for source in sources_for_country:
                    try:
                        count = await SCRAPERS[source](page, company_en, company_zh, ticker, region)
                        total += count
                    except Exception as e:
                        print(f"Error in {source}: {e}")
                await browser.close()

    print(f"\nTotal collected: {total} posts for '{company_en}'")

if __name__ == "__main__":
    company_en = input("English name: ")
    company_zh = input("Local language name (press Enter to skip): ")
    ticker = input("Ticker / code (press Enter to skip): ")
    region = input("Region (HK/JP/KR/TW/US): ")
    print("\nWhich sources? (press Enter for all, or comma-separated e.g. dcard,eastmoney,5ch)")
    sources_input = input("Sources: ").strip()
    sources = [s.strip() for s in sources_input.split(",")] if sources_input else None
    asyncio.run(run_all(company_en, company_zh, ticker, region, sources))