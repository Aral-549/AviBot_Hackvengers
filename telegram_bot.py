"""
AVI Bot — Telegram Link Collector & AI Content Assistant
--------------------------------------------------------
Receives links in Telegram, extracts content using the resilient scraper,
processes with AI (category, summary, tags), and stores in SQLite.
"""

import os
import sys
import time
import json
import logging
import requests
from pathlib import Path

# Local imports
from config import Config, is_valid_url
from content_extractor import extract_content
from ai_processor import process_content
import database as db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AVI_Bot")

db.init_db()

def send_message(bot_token: str, chat_id: str, text: str, parse_mode: str = "Markdown", max_retries: int = 3) -> bool:
    """Send text message to Telegram Chat with exponential backoff retry and plain text fallback."""
    if not bot_token or not chat_id:
        logger.warning("Telegram send_message skipped: missing bot_token or chat_id.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": False
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    current_parse_mode = parse_mode
    retry_delay = 1.0

    for attempt in range(1, max_retries + 1):
        try:
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200:
                return True

            logger.error(f"Telegram API Attempt {attempt}/{max_retries} Error ({res.status_code}): {res.text}")

            # Fallback to plain text on Markdown 400 Bad Request
            if res.status_code == 400 and current_parse_mode:
                logger.warning("Markdown formatting failed. Retrying in plain text mode...")
                payload.pop("parse_mode", None)
                current_parse_mode = None
                plain_res = requests.post(url, json=payload, timeout=15)
                if plain_res.status_code == 200:
                    return True

            # Sleep with exponential backoff on 429 or 5xx server errors
            if res.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                time.sleep(retry_delay)
                retry_delay *= 2

        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram network exception (attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
                retry_delay *= 2
        except Exception as e:
            logger.error(f"Unexpected Telegram send error: {e}")
            break

    # Final plain text fallback attempt
    if current_parse_mode:
        try:
            payload.pop("parse_mode", None)
            res = requests.post(url, json=payload, timeout=15)
            return res.status_code == 200
        except Exception as exc:
            logger.error(f"Final plain text fallback failed: {exc}")

    return False


# Track recently processed URLs per session to block in-process duplicates
_processing_urls: set = set()


def handle_url(bot_token: str, chat_id: str, url: str):
    """Process incoming URL sent via Telegram (idempotent — deduplicates in-flight and DB)."""
    dedup_key = f"{chat_id}:{url}"
    if dedup_key in _processing_urls:
        logger.info(f"Duplicate in-flight request ignored: {url}")
        return
    _processing_urls.add(dedup_key)

    try:
        send_message(bot_token, chat_id, f"🔎 *Processing link:* `{url}`\n_Extracting content \& generating AI summary..._")

        extracted = extract_content(url)
        if not extracted.get('success'):
            error_msg = extracted.get('error', 'Failed to extract web content.')
            send_message(bot_token, chat_id, f"❌ *Extraction Failed*\nURL: `{url}`\nError: {error_msg}")
            return

        # Process with AI
        ai_result = process_content(extracted)

        # Prepare database record
        category = ai_result.get('category', 'Uncategorized')
        summary = ai_result.get('summary', extracted.get('caption', ''))
        summary_source = ai_result.get('summary_source', 'ai_processor')
        video_summary = ai_result.get('video_summary', '')
        video_summary_status = ai_result.get('video_summary_status', '')
        tags = ai_result.get('tags', [])
        tags_str = tags if isinstance(tags, str) else ', '.join(tags)

        saved_id = db.save_content(
            url=url,
            platform=extracted.get('platform', 'web'),
            title=extracted.get('title', 'Untitled'),
            caption=extracted.get('caption', ''),
            image_url=extracted.get('image_url', ''),
            category=category,
            summary=summary,
            summary_source=summary_source,
            video_summary=video_summary,
            video_summary_status=video_summary_status,
            tags=tags_str,
            user_phone=chat_id
        )

        tag_list = [t.strip() for t in tags_str.split(',') if t.strip()] if isinstance(tags_str, str) else tags
        tags_formatted = ' '.join([f"#{t.replace(' ', '')}" for t in tag_list[:6]])

        reply_text = (
            f"✅ *Saved to AVI Bot Library* [\#{saved_id}]\n\n"
            f"📌 *Title:* {extracted.get('title', 'Untitled')}\n"
            f"🔗 *URL:* {url}\n"
            f"📁 *Category:* `{category}`\n"
            f"🏷️ *Tags:* {tags_formatted}\n\n"
            f"📝 *AI Summary:*\n{summary}\n\n"
            f"🌐 Dashboard: http://localhost:5000"
        )
        send_message(bot_token, chat_id, reply_text, parse_mode=None)  # plain text avoids Markdown parse errors
    finally:
        _processing_urls.discard(dedup_key)

def handle_command(bot_token: str, chat_id: str, text: str):
    """Handle Telegram bot commands."""
    cmd = text.split()[0].lower()

    if cmd in ['/start', '/help']:
        welcome = (
            "🤖 *Welcome to AVI Bot!*\n\n"
            "Send me any web link (articles, news, YouTube, docs) and I will:\n"
            "1. Scrape the content automatically\n"
            "2. Categorize & summarize it using AI\n"
            "3. Extract searchable tags & store it in your library\n\n"
            "*Available Commands:*\n"
            "• `/search <query>` - Search your saved links\n"
            "• `/stats` - View category & platform breakdown\n"
            "• `/random` - Resurface a random saved bookmark\n"
            "• `/categories` - List categories & record counts"
        )
        send_message(bot_token, chat_id, welcome)

    elif cmd == '/stats':
        stats = db.get_stats()
        cats = stats.get('categories', {}) or stats.get('by_category', {})
        cat_lines = '\n'.join([f"• `{k}`: {v}" for k, v in list(cats.items())[:8]])
        msg = (
            f"📊 *AVI Bot Library Statistics*\n\n"
            f"Total Saved Items: *{stats.get('total', 0)}*\n\n"
            f"*Top Categories:*\n{cat_lines or 'None yet'}"
        )
        send_message(bot_token, chat_id, msg)

    elif cmd == '/categories':
        cat_stats = db.get_category_stats()
        if not cat_stats:
            send_message(bot_token, chat_id, "📁 No categorized items found yet.")
            return
        lines = [f"• `{k}`: {v} item(s)" for k, v in list(cat_stats.items())[:15]]
        msg = f"📁 *AVI Bot Categories:*\n\n" + '\n'.join(lines)
        send_message(bot_token, chat_id, msg)

    elif cmd == '/random':
        items = db.get_random_content(count=1)
        if not items:
            send_message(bot_token, chat_id, "📭 No saved items in library yet. Send me a link to get started!")
            return
        item = items[0]
        msg = (
            f"🎲 *Random Resurface*\n\n"
            f"📌 *[{item.get('title', 'Untitled')}]({item.get('url', '')})*\n"
            f"📁 Category: `{item.get('category', 'Uncategorized')}`\n"
            f"📝 {(item.get('summary') or '')[:200]}..."
        )
        send_message(bot_token, chat_id, msg)

    elif cmd == '/search':
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            send_message(bot_token, chat_id, "⚠️ Usage: `/search <query>`")
            return
        query = parts[1]
        results = db.search_content(query, limit=5)
        if not results:
            send_message(bot_token, chat_id, f"🔍 No results found for `{query}`")
            return
        lines = [f"• [{r.get('title', 'Untitled')}]({r.get('url', '')}) (`{r.get('category', 'Uncategorized')}`)" for r in results]
        send_message(bot_token, chat_id, f"🔍 *Search Results for '{query}':*\n\n" + '\n'.join(lines))

def poll_telegram_bot():
    """Poll Telegram Bot API for incoming messages."""
    bot_token = Config.TELEGRAM_BOT_TOKEN or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not configured! Set it in .env or environment.")
        print("\n[!] Set TELEGRAM_BOT_TOKEN in .env to run the bot live.")
        print("[!] Example: TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyZ\n")
        return

    logger.info("Starting AVI Telegram Bot Listener (Polling mode)...")
    offset = 0
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"

    while True:
        try:
            res = requests.get(url, params={"offset": offset, "timeout": 20}, timeout=30)
            if res.status_code == 200:
                updates = res.json().get("result", [])
                for update in updates:
                    offset = update["update_id"] + 1
                    msg = update.get("message")  # ignore edited_message — Telegram fires it on URL preview unfurl, causing duplicate processing
                    if not msg:
                        continue

                    chat_id = str(msg["chat"]["id"])
                    text = msg.get("text", "").strip()
                    if not text:
                        continue

                    logger.info(f"Received message from chat {chat_id}: {text}")

                    if text.startswith('/'):
                        handle_command(bot_token, chat_id, text)
                    else:
                        # Extract URL from text
                        urls = [word for word in text.split() if is_valid_url(word)]
                        if urls:
                            for u in urls:
                                handle_url(bot_token, chat_id, u)
                        else:
                            send_message(bot_token, chat_id, "💡 Send me a valid web link (URL) or use `/help` to see commands.")

        except Exception as e:
            logger.error(f"Polling loop exception: {e}")
            time.sleep(3)

if __name__ == '__main__':
    poll_telegram_bot()
