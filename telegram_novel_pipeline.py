"""
Single-Call Novel Pipeline with Telegram Integration for Hermes Agent
----------------------------------------------------------------------
This module combines:
1. Novel metadata probing
2. Concurrent scraping & chapter caching
3. EPUB generation in batches of 100
4. Automated Telegram Document Delivery

Designed for extreme efficiency (1 single tool call, zero LLM back-and-forth overhead).
"""

import sys
import asyncio
import os
import re
import json
import requests

# Force UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from bs4 import BeautifulSoup
from ebooklib import epub
from playwright.async_api import async_playwright

BASE_URL = "https://novelfire.net/book"
OUTPUT_DIR = Path("epubs")
OUTPUT_DIR.mkdir(exist_ok=True)

CONTENT_SELECTORS = [
    "#chapter-container",
    ".chapter-content",
    ".content-inner",
    "#content",
    "article.chapter",
    ".reading-content",
    "div.text-left",
    ".chapter-body",
    "#chapter-content",
]

# ─── Telegram File Uploader ───────────────────────────────────────────────────

def send_telegram_document(bot_token: str, chat_id: str, file_path: str, caption: str = "") -> bool:
    """Sends an EPUB or PDF file directly to a Telegram Chat using the Telegram Bot API."""
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    path = Path(file_path)
    if not path.exists():
        print(f"[Telegram Error] File not found: {file_path}")
        return False
        
    try:
        with open(path, "rb") as f:
            files = {"document": (path.name, f, "application/epub+zip")}
            data = {"chat_id": chat_id, "caption": caption}
            response = requests.post(url, data=data, files=files, timeout=120)
            
        if response.status_code == 200:
            print(f"[Telegram Success] Sent {path.name} to Chat ID {chat_id}")
            return True
        else:
            print(f"[Telegram Failed] Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"[Telegram Exception] {e}")
        return False

# ─── Pipeline Helpers ─────────────────────────────────────────────────────────

def extract_slug(url_or_slug: str) -> str:
    url_or_slug = url_or_slug.strip().rstrip('/')
    if "/book/" in url_or_slug:
        return url_or_slug.split("/book/")[-1].split('/')[0]
    return url_or_slug

def clean_title(title: str, ch_num: int, novel_title: str) -> str:
    title = re.sub(r'\s*\[\s*\d+(?:,\d+)?\s*words?\s*\]', '', title, flags=re.I).strip()
    title = re.sub(rf'^{re.escape(novel_title)}\s*-?\s*', '', title, flags=re.I).strip()
    title = re.sub(r'^.*?-?Chapter\s+(\d+)\s*', r'Chapter \1 ', title, flags=re.I).strip()
    m = re.match(r'^Chapter\s+(\d+)\s*(.*)', title, flags=re.I)
    if m:
        c_num = int(m.group(1))
        rest = m.group(2).strip()
        rest = re.sub(rf'^-\s*{c_num}\s*', '', rest).strip()
        rest = re.sub(rf'^-\s*', '', rest).strip()
        rest = re.sub(rf'^{c_num}\.?\s*', '', rest).strip()
        rest = re.sub(rf'^[:\-\u2013\u2014\s]+', '', rest).strip()
        return f"Chapter {c_num}: {rest}" if rest else f"Chapter {c_num}"
    return title

async def scrape_chapter(page, slug: str, ch_num: int) -> tuple:
    url = f"{BASE_URL}/{slug}/chapter-{ch_num}"
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        if resp and resp.status == 404:
            return None, None, False
        await page.wait_for_timeout(1000)
        
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        page_title = (await page.title()).lower()
        
        if ("page not found" in page_title or "404 not found" in page_title or page_title.strip() == "404") or \
           ("not found" in page_title and "chapter" not in page_title) or \
           ("404" in page_title and "chapter" not in page_title):
            return None, None, False
            
        body = None
        for sel in CONTENT_SELECTORS:
            body = soup.select_one(sel)
            if body and len(body.get_text(strip=True)) > 100:
                break
        if body is None:
            divs = soup.find_all("div")
            if divs:
                body = max(divs, key=lambda d: len(d.find_all("p")))
                
        if body is None or len(body.get_text(strip=True)) < 50:
            return None, None, False
            
        for tag in body.find_all(["script", "style", "ins", "iframe", "nav", "button", "form", "noscript"]):
            tag.decompose()
            
        raw_title = soup.find("h1") or soup.find("h2")
        ch_title = raw_title.get_text(strip=True) if raw_title else f"Chapter {ch_num}"
        return ch_title, str(body), True
    except Exception:
        return None, None, False

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '_', str(name)).strip()

def create_epub_file(slug: str, title: str, author: str, chapters: list, range_str: str) -> Path:
    book = epub.EpubBook()
    book.set_identifier(f"{slug}-{range_str}")
    book.set_title(f"{title} ({range_str})")
    book.set_language("en")
    book.add_author(author)
    
    css = epub.EpubItem(
        uid="style", file_name="style/style.css", media_type="text/css",
        content="body { font-family: Georgia, serif; line-height: 1.6; padding: 5%; }\nh2 { text-align: center; margin-bottom: 1.5em; }\np { text-indent: 1em; margin-bottom: 0.5em; }"
    )
    book.add_item(css)
    
    spine, toc = ["nav"], []
    for ch in chapters:
        c_num = ch["num"]
        c_title = clean_title(ch["title"], c_num, title)
        c_item = epub.EpubHtml(title=c_title, file_name=f"chap_{c_num:04d}.xhtml", lang="en")
        c_item.content = f"<html><head></head><body><h2>{c_title}</h2>{ch['content']}</body></html>"
        c_item.add_item(css)
        book.add_item(c_item)
        spine.append(c_item)
        toc.append(c_item)
        
    book.toc = tuple(toc)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine
    
    safe_name = sanitize_filename(f"{title} ({range_str}).epub")
    output_path = OUTPUT_DIR / safe_name
    epub.write_epub(output_path, book)
    return output_path

# ─── 1-Call Combined Pipeline ─────────────────────────────────────────────────

async def process_novel_to_telegram_async(
    url_or_slug: str,
    telegram_chat_id: str = None,
    telegram_bot_token: str = None,
    batch_size: int = 100,
    concurrency: int = 5
) -> dict:
    """
    Executes the entire workflow in a single function call:
    1. Probes title, author, chapter count.
    2. Concurrent scrapes missing chapters.
    3. Packages into EPUB batches of 100.
    4. Automatically uploads all generated EPUBs to Telegram.
    """
    slug = extract_slug(url_or_slug)
    url = f"{BASE_URL}/{slug}"
    
    print(f"[*] Starting 1-Call Novel Pipeline for: {slug}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Probe metadata
        await page.goto(url, wait_until="domcontentloaded")
        page_title = await page.title()
        clean_novel_title = re.sub(r'\s*-\s*Novel\s*Fire.*$', '', page_title, flags=re.I).strip()
        
        author = "Unknown"
        author_el = await page.query_selector('a[href*="/author/"]')
        if author_el:
            author = await author_el.inner_text()
            
        await page.goto(f"{url}/chapters", wait_until="domcontentloaded")
        total_chapters = await page.evaluate(r'''() => {
            let el = document.getElementById('gotochapno');
            if (el) return parseInt(el.getAttribute('max'));
            let max = 0;
            for (let a of document.querySelectorAll('a')) {
                if (a.href && a.href.includes('chapter-')) {
                    let m = a.href.match(/chapter-(\d+)/);
                    if (m) { let n = parseInt(m[1]); if (n > max) max = n; }
                }
            }
            return max;
        }''')
        await page.close()
        
        if not total_chapters or total_chapters == 0:
            total_chapters = 100 # Fallback
            
        print(f"[*] Probed: Title='{clean_novel_title}', Author='{author}', Chapters={total_chapters}")
        
        # Scrape chapters
        cache_dir = Path(f"chapters_{slug.replace('-', '_')}")
        cache_dir.mkdir(exist_ok=True)
        
        needed = [n for n in range(1, total_chapters + 1) if not (cache_dir / f"chapter_{n:04d}.json").exists()]
        
        if needed:
            print(f"[*] Scraping {len(needed)} missing chapters...")
            sem = asyncio.Semaphore(concurrency)
            async def worker(ch_num):
                async with sem:
                    w_page = await browser.new_page()
                    for attempt in range(1, 4):
                        ch_title, html_content, success = await scrape_chapter(w_page, slug, ch_num)
                        if success:
                            data = {"num": ch_num, "title": ch_title, "content": html_content}
                            with open(cache_dir / f"chapter_{ch_num:04d}.json", "w", encoding="utf-8") as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                            break
                        await asyncio.sleep(1.5)
                    await w_page.close()
            
            await asyncio.gather(*[worker(n) for n in needed])
            
        await browser.close()

    # Package EPUBs in batches of 100
    chapters = []
    for n in range(1, total_chapters + 1):
        fp = cache_dir / f"chapter_{n:04d}.json"
        if fp.exists():
            with open(fp, "r", encoding="utf-8") as f:
                chapters.append(json.load(f))
    chapters.sort(key=lambda x: x["num"])

    generated_epubs = []
    for i in range(0, len(chapters), batch_size):
        chunk = chapters[i:i + batch_size]
        c_start, c_end = chunk[0]["num"], chunk[-1]["num"]
        epub_path = create_epub_file(slug, clean_novel_title, author, chunk, f"{c_start}-{c_end}")
        generated_epubs.append(str(epub_path))
        
    print(f"[OK] Created {len(generated_epubs)} EPUB batch files.")

    # Telegram Delivery
    sent_count = 0
    bot_token = telegram_bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = telegram_chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    
    if bot_token and chat_id:
        print(f"[*] Uploading EPUBs to Telegram Chat ID: {chat_id}")
        for path in generated_epubs:
            caption = f"📖 {clean_novel_title}\nAuthor: {author}\nFile: {Path(path).name}"
            success = send_telegram_document(bot_token, chat_id, path, caption)
            if success:
                sent_count += 1
    else:
        print("[!] Telegram credentials not set. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to auto-send.")

    return {
        "status": "success",
        "title": clean_novel_title,
        "author": author,
        "total_chapters": total_chapters,
        "epub_count": len(generated_epubs),
        "epubs": generated_epubs,
        "telegram_sent": sent_count
    }

def process_novel_to_telegram(
    url_or_slug: str,
    telegram_chat_id: str = None,
    telegram_bot_token: str = None,
    batch_size: int = 100
) -> dict:
    return asyncio.run(process_novel_to_telegram_async(url_or_slug, telegram_chat_id, telegram_bot_token, batch_size))

# ─── Hermes Tool Definition ───────────────────────────────────────────────────

HERMES_EFFICIENT_TOOL = {
    "type": "function",
    "function": {
        "name": "process_novel_to_telegram",
        "description": "Scrapes a novel from a NovelFire URL/slug, packages it into EPUB batches of 100 chapters, and sends all EPUBs directly to Telegram in a single call.",
        "parameters": {
            "type": "object",
            "properties": {
                "url_or_slug": {
                    "type": "string",
                    "description": "NovelFire novel URL or slug (e.g. 'https://novelfire.net/book/my-living-shadow-system-devours-to-make-me-stronger')"
                },
                "telegram_chat_id": {
                    "type": "string",
                    "description": "Telegram user or channel chat_id to send the files to."
                }
            },
            "required": ["url_or_slug"]
        }
    }
}
