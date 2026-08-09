# Avi

**Try it now: [t.me/Avi514_bot](https://t.me/Avi514_bot)** — send it a link and see it work.
**Live dashboard: [avi-bot-production-b769.up.railway.app/dashboard](https://avi-bot-production-b769.up.railway.app/dashboard)**

Avi turns any link you send it — Instagram, YouTube, TikTok, Twitter/X, Reddit, LinkedIn, Pinterest, Facebook, or a plain blog post — into a searchable, categorized, AI-summarized entry in your personal knowledge library. Send it a URL over Telegram or WhatsApp; it scrapes the content, figures out what it is, writes a one-line hook summary and (for video) a longer summary, tags it, and files it into one of 100 preset categories. Everything lands in a Flask dashboard you can search, filter, and export.

## What it does

- **Capture** — send a link via Telegram or WhatsApp (Twilio); Avi extracts it in the background and replies with the result.
- **Extract** — a 5-layer fallback scraper (platform-specific parser → generic OpenGraph/meta tags → headless browser via Playwright → yt-dlp → raw URL fallback) guarantees every link resolves to *something*, even paywalled or JS-heavy pages.
- **Understand** — an LLM pipeline (OpenRouter → Groq → Gemini, with a rule-based fallback if all three are unavailable) assigns a category, writes a short "hook" summary, generates a detailed multi-sentence summary for video/reel content via Gemini multimodal, and extracts 8–12 searchable tags.
- **Organize** — SQLite + FTS5 full-text search, category/platform filters, user-created collections, tag browsing, and a daily activity heatmap.
- **Resurface** — WhatsApp commands (`surprise me`, `motivate me`, `teach me`, `feed me`, `my streak`, `ask: <question>`) and scheduled daily-dose / weekly-digest messages bring old saves back to the top.
- **Ask your library** — a lightweight RAG flow (`ask: <question>`) searches your saved content and answers using only what you've actually saved.
- **Export** — CSV export and a full Obsidian-compatible Markdown vault export (one note per saved item, with YAML frontmatter and tags).

## Architecture

```
telegram_bot.py   — Telegram polling loop: receives links/commands, replies with results
app.py            — Flask app: dashboard, REST API, WhatsApp (Twilio) webhook, scheduled digests
content_extractor.py — 5-layer scraping fallback chain per platform
ai_processor.py   — LLM provider router (OpenRouter/Groq/Gemini) + category/summary/tag generation
database.py       — SQLite access layer, FTS5 search, collections, streaks, Obsidian/JSONL backup export
config.py         — env-driven settings, category list, all LLM prompts
```

Two independent entry points share the same database and AI/extraction pipeline: `app.py` (web dashboard + WhatsApp) and `telegram_bot.py` (Telegram). Run them as separate processes.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in API keys below
python app.py           # dashboard on :5000
python telegram_bot.py  # separate process, only if using Telegram intake
```

### Environment variables

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` / `GROQ_API_KEY` / `GEMINI_API_KEY` | At least one required for AI categorization/summarization; falls back to rule-based logic if none are set |
| `ACTIVE_AI_PROVIDER` | Preferred provider first in the fallback chain (`openrouter`, `groq`, or `gemini`) |
| `TELEGRAM_BOT_TOKEN` | Required only for `telegram_bot.py` |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_PHONE_NUMBER` | Required only for WhatsApp intake/notifications |
| `YTDLP_ENABLED` | Toggle the yt-dlp extraction layer |
| `SECRET_KEY` | Flask session secret — set a real value in production |

## Known limitations

- AI categorization can be unreliable when the LLM doesn't return a clean category name (see fallback fuzzy-matching in `categorize_content`) — it's under active fixing.
- No `UNIQUE` constraint on saved URLs yet; concurrent saves of the same link can create duplicate rows.
- Playwright (headless-browser fallback layer) is optional — install `playwright` and run `playwright install chromium` if you want it; the pipeline degrades gracefully without it.
- Backup ledger and Obsidian export write to a path relative to the app directory — on hosts with ephemeral filesystems, only the SQLite DB persists unless you point `DATABASE_PATH` (and equivalent) at mounted storage.

## Tech stack

Flask, SQLite (FTS5), BeautifulSoup4, yt-dlp, Playwright (optional), Twilio, OpenRouter/Groq/Gemini APIs.
