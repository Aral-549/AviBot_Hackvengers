"""
Configuration management for AVI Bot
"""

import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / '.env'
load_dotenv(env_path, override=True)


class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    FLASK_BASE_URL = os.getenv('FLASK_BASE_URL', '')

    # Telegram Integration
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

    # OpenRouter AI
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
    OPENROUTER_BASE_URL = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
    OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'openrouter/auto')

    # Groq AI
    GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
    GROQ_BASE_URL = os.getenv('GROQ_BASE_URL', 'https://api.groq.com/openai/v1')
    GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')

    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_BASE_URL = os.getenv('GEMINI_BASE_URL', 'https://generativelanguage.googleapis.com/v1')
    GEMINI_UPLOAD_BASE_URL = os.getenv('GEMINI_UPLOAD_BASE_URL', 'https://generativelanguage.googleapis.com/v1/files')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash-001')
    GEMINI_VIDEO_MODEL = os.getenv('GEMINI_VIDEO_MODEL', 'gemini-2.0-flash-001')

    ACTIVE_AI_PROVIDER = os.getenv('ACTIVE_AI_PROVIDER', 'openrouter')
    DATABASE_PATH = os.getenv('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'social_saver.db'))
    ITEMS_PER_PAGE = int(os.getenv('ITEMS_PER_PAGE', 20))
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 5000))

    # Media & Scraper Limits
    MAX_MEDIA_DOWNLOAD_BYTES = int(os.getenv('MAX_MEDIA_DOWNLOAD_BYTES', 50 * 1024 * 1024))
    USER_AGENT = os.getenv('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', 30))
    YTDLP_ENABLED = os.getenv('YTDLP_ENABLED', 'True').lower() == 'true'

    # Telegram Integration
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    YTDLP_COOKIES_FILE = os.getenv('YTDLP_COOKIES_FILE', '')

    # Platform patterns
    PLATFORM_PATTERNS = {
        'instagram': ['instagram.com', 'instagr.am'],
        'twitter': ['twitter.com', 'x.com'],
        'facebook': ['facebook.com', 'fb.com'],
        'youtube': ['youtube.com', 'youtu.be'],
        'tiktok': ['tiktok.com'],
        'linkedin': ['linkedin.com'],
        'reddit': ['reddit.com', 'redd.it'],
        'pinterest': ['pinterest.com', 'pin.it'],
        'blog': []
    }

    ALLOWED_PLATFORMS = ['instagram', 'twitter', 'facebook', 'youtube', 'tiktok',
                         'linkedin', 'reddit', 'pinterest', 'blog']

    # ── 100 Categories ─────────────────────────────────────────────────────────
    DEFAULT_CATEGORIES = [
        # Technology (12)
        'Artificial Intelligence', 'Machine Learning', 'Programming & Coding',
        'Web Development', 'Mobile Apps', 'Cybersecurity', 'Cloud Computing',
        'Data Science', 'Blockchain & Crypto', 'Tech Gadgets & Reviews',
        'Open Source', 'Software Engineering',

        # Business & Finance (12)
        'Entrepreneurship', 'Startups & Funding', 'Marketing & Growth',
        'SEO & Content Marketing', 'Social Media Marketing', 'E-Commerce',
        'Personal Finance', 'Stock Market & Investing', 'Real Estate',
        'Business Strategy', 'Remote Work & Productivity', 'Career Development',

        # Health & Wellness (10)
        'Fitness & Workouts', 'Yoga & Stretching', 'Nutrition & Diet',
        'Mental Health & Mindfulness', 'Weight Loss', 'Bodybuilding',
        'Running & Cardio', 'Sleep & Recovery', 'Supplements & Biohacking',
        'Medical & Health News',

        # Food & Cooking (8)
        'Recipes & Cooking', 'Baking & Desserts', 'Meal Prep',
        'Vegan & Plant-Based', 'Street Food & Restaurants',
        'Coffee & Beverages', 'Wine & Cocktails', 'Food Science',

        # Entertainment (10)
        'Movies & Cinemas', 'TV Shows & Series', 'Anime & Manga',
        'Stand-Up Comedy', 'Music & Artists', 'Podcasts',
        'Gaming & Esports', 'Books & Literature', 'Streaming & Reviews',
        'Celebrity & Pop Culture',

        # Travel & Adventure (8)
        'Travel Destinations', 'Budget Travel & Backpacking',
        'Luxury Travel', 'Road Trips', 'Solo Travel',
        'Travel Tips & Hacks', 'Adventure Sports', 'Digital Nomad Life',

        # Education & Learning (8)
        'Science & Research', 'History & Archaeology', 'Space & Astronomy',
        'Mathematics & Logic', 'Language Learning', 'Online Courses',
        'Study Tips & Productivity', 'Philosophy & Critical Thinking',

        # Creative & Arts (8)
        'Photography', 'Graphic Design & UI/UX', 'Video Production',
        'Digital Art & Illustration', 'Architecture & Interiors',
        'Fashion & Style', 'DIY & Crafts', 'Writing & Storytelling',

        # Lifestyle (8)
        'Minimalism & Organization', 'Parenting & Family',
        'Pets & Animals', 'Relationships & Dating',
        'Luxury & Lifestyle', 'Motivation & Self-Help',
        'Spirituality & Religion', 'Astrology & Wellness',

        # News & Society (8)
        'World News', 'Politics & Policy', 'Environment & Climate',
        'Human Rights & Social Justice', 'Economics & Global Markets',
        'Science News', 'Sports News', 'Local & Community',

        # Sports (6)
        'Football & Soccer', 'Cricket', 'Basketball & NBA',
        'Tennis & Racket Sports', 'Combat Sports & MMA', 'Motorsports & F1',

        # Miscellaneous (2)
        'Viral & Trending', 'Other',
    ]

    # ── Prompts ─────────────────────────────────────────────────────────────────

    CATEGORY_PROMPT = """You are an expert content librarian. Assign exactly ONE category to this saved link.

AVAILABLE CATEGORIES:
{categories}

CONTENT:
- URL: {url}
- Title: {title}
- Description: {caption}

STRICT RULES:
1. Output ONLY the exact category name from the list — nothing else. No punctuation, no quotes, no explanation.
2. Use the URL domain as your PRIMARY signal, then the title, then the description.
3. Never invent a new category. Use "Other" only as a last resort.

DOMAIN → CATEGORY SIGNAL GUIDE (follow this closely):
- github.com, gitlab.com → "Open Source" or "Programming & Coding" or "Web Development" or "Cybersecurity" (pick by repo topic)
- youtube.com, youtu.be, youtube.com/shorts → use TITLE to decide category (fitness/yoga/recipe/tech/etc.)
- news.ycombinator.com, hn.algolia.com → "Programming & Coding" or "Entrepreneurship" or "Artificial Intelligence" (pick by post title)
- devpost.com → "Entrepreneurship" or "Programming & Coding"
- reddit.com/r/finance, r/stocks → "Stock Market & Investing"
- reddit.com/r/MachineLearning, r/programming → "Machine Learning" or "Programming & Coding"
- twitter.com, x.com → use title for topic
- medium.com, substack.com → use title for topic
- wikipedia.org → use article subject
- netflix.com, imdb.com → "Movies & Cinemas"
- spotify.com → "Music & Artists"
- twitch.tv → "Gaming & Esports"

EXAMPLES:
- github.com/usestrix/strix (AI security scanner) → Cybersecurity
- news.ycombinator.com (Show HN: I built a compiler) → Programming & Coding
- youtube.com/shorts/xyz (morning yoga flow) → Yoga & Stretching
- devpost.com/hackathon → Entrepreneurship
- youtube.com/watch?v=xyz (Gordon Ramsay scrambled eggs) → Recipes & Cooking
- wikipedia.org/wiki/Artificial_intelligence → Artificial Intelligence
- medium.com (How I got 10k users in 30 days) → Marketing & Growth
- github.com/openai/gpt-4 → Artificial Intelligence

Category:"""

    SUMMARY_PROMPT = """You are a viral content writer. Your job is to write one irresistible hook sentence for a saved piece of content — the kind that makes someone stop scrolling.

CONTENT:
- Platform: {platform}
- Title: {title}
- Description: {caption}

RULES:
1. Return ONLY the one-liner — no labels, no quotes, no explanation.
2. Maximum 20 words.
3. Do NOT just rephrase the title. Add curiosity, urgency, or value.
4. No emojis, no hashtags, no markdown.
5. Write in second person ("you") or use an action verb to create energy.
6. If the content is technical, highlight the outcome/benefit, not the method.

EXAMPLES:
Title: "How to negotiate your salary" → You're leaving money on the table every time you skip this one conversation.
Title: "React hooks explained" → Finally understand React hooks without the confusion that killed your last project.
Title: "Sourdough bread recipe" → The beginner sourdough recipe that actually works on the first try.
Title: "Morning routine tips" → The 10-minute morning habit that separates productive people from everyone else.

One-liner:"""

    VIDEO_SUMMARY_PROMPT = """You are analyzing a saved short-form video or reel.

KNOWN METADATA:
- Platform: {platform}
- Title: {title}
- Caption: {caption}

TASK:
Describe what actually happens in the video. Prefer visible actions, spoken instructions, demonstrations, scene changes, and the concrete outcome.

RULES:
1. Return ONLY the summary sentence.
2. Maximum 30 words.
3. Be factual, direct, and specific.
4. Do not write marketing copy, hooks, emojis, hashtags, or quotes.
5. Do not repeat the caption unless the video evidence supports it.
6. If the video is instructional, state the main task, method, or takeaway.

Summary:"""

    IMAGE_SUMMARY_PROMPT = """You are looking at a thumbnail or still image from saved content.

KNOWN METADATA:
- Platform: {platform}
- Title: {title}
- Caption: {caption}

TASK:
Write one factual sentence describing the visible scene or likely action, using the image first and the metadata only to disambiguate.

RULES:
1. Return ONLY the summary sentence.
2. Maximum 25 words.
3. No hype, no quotes, no emojis, no hashtags.
4. If the image is too ambiguous, describe it cautiously.

Summary:"""

    METADATA_SUMMARY_PROMPT = """You are summarizing saved content from metadata only.

AVAILABLE METADATA:
- URL: {url}
- Platform: {platform}
- Title: {title}
- Caption: {caption}

TASK:
Write one cautious sentence about what the content is likely about.

RULES:
1. Return ONLY the summary sentence.
2. Maximum 25 words.
3. Be factual and restrained.
4. Do not pretend you watched the video or saw the full content.
5. No hooks, no hype, no emojis, no hashtags, no quotes.

Summary:"""

    DETAILED_VIDEO_SUMMARY_PROMPT = """You are a video content analyst. Your job is to provide a clear, informative summary of a video based on what you observe.

KNOWN METADATA:
- Platform: {platform}
- Title: {title}
- Caption: {caption}

TASK:
Write a 3-5 sentence summary covering:
1. What the video shows or demonstrates
2. Key points, steps, or arguments made
3. The main takeaway or conclusion

RULES:
1. Return ONLY the summary paragraph - no labels, no headers, no bullet points.
2. Maximum 80 words.
3. Be factual and descriptive - describe what actually happens.
4. Do NOT write marketing copy or hooks.
5. No emojis, no hashtags, no quotes.
6. If it is a tutorial, list the main steps or techniques shown.
7. If it is entertainment, describe the premise and notable moments.
8. If the content is ambiguous, be honest about what you can and cannot determine.

Summary:"""

    TAGS_PROMPT = """You are a search engine optimizer. Extract highly searchable tags from a piece of saved content so the user can find it later by keyword.

CONTENT:
- URL: {url}
- Platform: {platform}
- Title: {title}
- Description: {caption}

RULES:
1. Return ONLY comma-separated tags — no explanation, no numbering, no extra text.
2. Generate between 8 and 12 tags.
3. Use lowercase. Hyphenate multi-word tags: "machine-learning", "home-workout".
4. Mix broad tags (e.g. "fitness") with specific ones (e.g. "beginner-workout", "no-equipment").
5. Include: main topic, subtopics, target audience, content format (e.g. tutorial, recipe, review), mood/style.
6. Avoid useless generic tags like "post", "content", "link", "video", "article".
7. Include the platform name as a tag if it's a social platform.

EXAMPLES:
Title: "10 Python tricks every developer should know" →
python, programming, developer-tips, code-quality, python-tricks, software-engineering, beginner-friendly, tutorial, productivity, clean-code

Title: "Budget travel in Southeast Asia" →
travel, southeast-asia, budget-travel, backpacking, travel-tips, thailand, vietnam, solo-travel, cheap-flights, digital-nomad

Tags:"""

    RAG_PROMPT = """You are a personal knowledge assistant. The user has saved a collection of links with AI-generated summaries, categories, and tags. Your job is to answer their question using ONLY the saved content provided below.

USER QUESTION:
{question}

SAVED CONTENT (most relevant matches):
{context}

RULES:
1. Answer conversationally — like a smart friend who has read all their saves.
2. If the answer is found in the saves, cite the title and provide the URL.
3. If multiple saves are relevant, mention all of them briefly.
4. If NO saves are relevant, say: "I couldn't find anything about that in your saves. Try saving some content on this topic first!"
5. Keep the response under 200 words — this will be sent via WhatsApp.
6. Never make up information. Only use what's in the provided saves.
7. Format for WhatsApp: use line breaks, no markdown headers, no bullet symbols.

RESPONSE:"""

    DAILY_DIGEST_PROMPT = """You are a personal curator sending a warm, engaging morning message to someone about content they forgot they saved.

USER'S TOP CATEGORIES THIS WEEK:
{top_categories}

FEATURED SAVE:
- Title: {title}
- Category: {category}
- Summary: {summary}
- Saved: {time_ago}
- URL: {url}

RULES:
1. Write a short, warm WhatsApp message (under 150 words).
2. Start with a friendly morning greeting tied to the content topic.
3. Remind them why this save matters or what they might gain from it.
4. End with a gentle call to action to revisit it.
5. Use 1–2 emojis max. No markdown. WhatsApp-friendly line breaks.
6. Make it feel personal, not automated.

EXAMPLE TONE:
"Good morning! ☀️ You saved this one 3 weeks ago and never got back to it...
📌 How to negotiate a raise
Knowing this could literally change your next salary conversation.
Worth 5 minutes today 👉 [url]"

Message:"""

    DUPLICATE_CHECK_PROMPT = """You are a content deduplication engine. Determine if two pieces of content are about the same topic, even if the URLs or exact wording differ.

EXISTING SAVE:
- Title: {existing_title}
- Summary: {existing_summary}
- URL: {existing_url}

NEW CONTENT:
- Title: {new_title}
- Summary: {new_summary}
- URL: {new_url}

RULES:
1. Return ONLY one word: "DUPLICATE" or "UNIQUE".
2. Mark as DUPLICATE if: same video/article on different URL formats, same news story from different outlets, same tutorial/recipe with minor variations.
3. Mark as UNIQUE if: same broad topic but meaningfully different content, perspective, or format.
4. Do not consider platform differences alone as making content unique.

Result:"""

    COLLECTION_SUGGEST_PROMPT = """You are a personal content organizer. Based on a user's saved content, suggest the most fitting collection name for a new save.

USER'S EXISTING COLLECTIONS:
{existing_collections}

NEW CONTENT BEING SAVED:
- Title: {title}
- Category: {category}
- Tags: {tags}
- Summary: {summary}

RULES:
1. If the new content fits an existing collection well, return that EXACT collection name.
2. If no existing collection fits, suggest a SHORT new collection name (2–4 words max).
3. Return ONLY the collection name — nothing else.
4. Collection names should be intuitive, personal, and action-oriented.
   Good: "Morning Reads", "Startup Ideas", "Workout Plans", "Python Resources"
   Bad: "Technology", "Content", "Saved Items"

Collection:"""


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    DEBUG = True
    TESTING = True


def get_config():
    env = os.getenv('FLASK_ENV', 'development')
    return {'development': DevelopmentConfig, 'production': ProductionConfig,
            'testing': TestingConfig}.get(env, DevelopmentConfig)


def detect_platform(url: str) -> str:
    url_lower = url.lower()
    for platform, patterns in Config.PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if pattern in url_lower:
                return platform
    return 'blog'


def is_valid_url(url: str) -> bool:
    from urllib.parse import urlparse
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False
