# Avi — AI-Powered Link Library

> Save any link via Telegram. AVI Bot scrapes, categorises, summarises, and stores it using AI — then surfaces it through a beautiful web dashboard.

## What it does

Send any URL to the Telegram bot → AVI Bot automatically:
1. **Scrapes** the page (5-layer fallback: Requests → OG Tags → Playwright → yt-dlp → Raw)
2. **Categorises** it with AI (OpenRouter → Groq → Gemini → algorithmic fallback)
3. **Summarises** it into a one-liner hook sentence
4. **Extracts tags** and stores everything in SQLite
5. **Replies instantly** in Telegram with the result
6. Viewable on a **premium dark web dashboard** at `localhost:5000`

## Tech Stack

| Layer | Tech |
|---|---|
| Bot | Python + python-telegram-bot (polling) |
| AI | OpenRouter (claude/mistral/llama), Groq, Gemini |
| Scraping | requests, BeautifulSoup, Playwright, yt-dlp |
| Database | SQLite (WAL mode) + JSONL backup ledger |
| Web Dashboard | Flask + Jinja2 |
| Export | Obsidian Markdown vault, CSV |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your API keys
python3 app.py         # web dashboard → http://localhost:5000
python3 telegram_bot.py  # Telegram listener
```

## Environment Variables

See `.env.example` for all required keys:
- `TELEGRAM_BOT_TOKEN`
- `OPENROUTER_API_KEY`
- `GROQ_API_KEY`
- `GEMINI_API_KEY`

## Features

- **Zero-failure AI chain** — 4-tier LLM fallback, never drops a link
- **Multi-layer scraper** — handles SPAs, paywalls, video platforms
- **Obsidian sync** — export your entire library as Markdown notes
- **Collections** — organise saved links into folders
- **Full-text search** — FTS5 SQLite index for instant search
- **Duplicate guard** — same URL never processed twice
