"""
Database module for AVI Bot / AVI Bot
Handles SQLite operations for storing and retrieving saved content.
Features: Content Indexing, FTS / LIKE Search Fallback, Tag Parsing,
Category Statistics, and Connection Management.
"""

import sqlite3
import os
import json
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager
from config import Config

# Database file path & Backup directory
DB_PATH = getattr(Config, 'DATABASE_PATH', None) or os.getenv('DATABASE_PATH') or os.path.join(os.path.dirname(__file__), 'avi_bot.db')
BACKUP_DIR = os.getenv('BACKUP_DIR', os.path.join(os.path.dirname(__file__), 'backups'))
BACKUP_FILE = os.path.join(BACKUP_DIR, 'link_vault_backup.jsonl')


def append_to_backup_ledger(record: Dict) -> None:
    """Append every saved link to a JSON Lines backup ledger for zero data-loss durability."""
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        with open(BACKUP_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception as exc:
        print(f"Backup ledger append error: {exc}")


def get_db_connection() -> sqlite3.Connection:
    """Get a new SQLite database connection with WAL mode enabled for concurrent safety."""
    db_path = getattr(Config, 'DATABASE_PATH', None) or os.getenv('DATABASE_PATH') or DB_PATH
    db_dir = os.path.dirname(os.path.abspath(db_path))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA journal_mode=WAL;')
        conn.execute('PRAGMA synchronous=NORMAL;')
    except Exception:
        pass
    return conn


@contextmanager
def get_db():
    """Context manager for clean connection handling and automatic commit/rollback."""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize database tables, WAL mode, indexes, FTS virtual tables, and triggers."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('PRAGMA journal_mode=WAL;')
            cursor.execute('PRAGMA synchronous=NORMAL;')
        except Exception:
            pass

        # Create main table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                platform TEXT NOT NULL,
                title TEXT,
                caption TEXT,
                image_url TEXT,
                media_extraction_status TEXT,
                media_extraction_error TEXT,
                category TEXT,
                summary TEXT,
                summary_source TEXT,
                video_summary TEXT,
                video_summary_status TEXT,
                tags TEXT,
                user_phone TEXT,
                collection TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Auto-migrate missing columns if upgrading existing DB
        for col_name in (
            'image_url',
            'media_extraction_status',
            'media_extraction_error',
            'summary_source',
            'video_summary',
            'video_summary_status',
            'collection'
        ):
            try:
                cursor.execute(f'ALTER TABLE saved_content ADD COLUMN {col_name} TEXT')
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Create B-Tree Indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_platform ON saved_content(platform)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON saved_content(category)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_phone ON saved_content(user_phone)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON saved_content(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_collection ON saved_content(collection)')
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_url_unique ON saved_content(url)')

        # Full-Text Search (FTS5) Table & Triggers for Content Indexing
        try:
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS saved_content_fts USING fts5(
                    title, caption, tags, summary, category, url,
                    content='saved_content', content_rowid='id'
                )
            ''')

            # Triggers to automatically keep FTS in sync with saved_content
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS saved_content_ai AFTER INSERT ON saved_content BEGIN
                    INSERT INTO saved_content_fts(rowid, title, caption, tags, summary, category, url)
                    VALUES (new.id, new.title, new.caption, new.tags, new.summary, new.category, new.url);
                END;
            ''')
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS saved_content_ad AFTER DELETE ON saved_content BEGIN
                    INSERT INTO saved_content_fts(saved_content_fts, rowid, title, caption, tags, summary, category, url)
                    VALUES('delete', old.id, old.title, old.caption, old.tags, old.summary, old.category, old.url);
                END;
            ''')
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS saved_content_au AFTER UPDATE ON saved_content BEGIN
                    INSERT INTO saved_content_fts(saved_content_fts, rowid, title, caption, tags, summary, category, url)
                    VALUES('delete', old.id, old.title, old.caption, old.tags, old.summary, old.category, old.url);
                    INSERT INTO saved_content_fts(rowid, title, caption, tags, summary, category, url)
                    VALUES (new.id, new.title, new.caption, new.tags, new.summary, new.category, new.url);
                END;
            ''')

            # Populate FTS index for existing rows not yet indexed
            cursor.execute('''
                INSERT INTO saved_content_fts(rowid, title, caption, tags, summary, category, url)
                SELECT id, title, caption, tags, summary, category, url FROM saved_content
                WHERE id NOT IN (SELECT rowid FROM saved_content_fts)
            ''')
        except sqlite3.OperationalError as e:
            print(f"FTS initialization note: {e}")

    init_collections_table()
    print("Database & Backup Ledger initialized successfully!")


OBSIDIAN_VAULT_DIR = os.getenv('OBSIDIAN_VAULT_DIR', os.path.join(os.path.dirname(__file__), 'obsidian_vault', 'notes'))


def export_to_obsidian_note(record: dict) -> str:
    """Export a saved link record as a structured Obsidian Markdown note with YAML frontmatter."""
    try:
        os.makedirs(OBSIDIAN_VAULT_DIR, exist_ok=True)
        title = record.get('title') or 'Untitled Note'
        url = record.get('url') or ''
        category = record.get('category') or 'Uncategorized'
        summary = record.get('summary') or record.get('caption') or 'No summary available.'
        tags_str = record.get('tags') or ''
        
        if isinstance(tags_str, str):
            tags_list = [t.strip().replace(' ', '-') for t in tags_str.split(',') if t.strip()]
        elif isinstance(tags_str, list):
            tags_list = [str(t).strip().replace(' ', '-') for t in tags_str]
        else:
            tags_list = []

        yaml_tags = '\n'.join([f"  - {t}" for t in tags_list]) if tags_list else "  - uncategorized"
        md_hashtags = ' '.join([f"#{t}" for t in tags_list]) if tags_list else "#bookmark"
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        slug = re.sub(r'[^\w\s-]', '', title).strip().lower()
        slug = re.sub(r'[-\s]+', '-', slug)[:60] or f"note-{record.get('id', '1')}"
        filepath = os.path.join(OBSIDIAN_VAULT_DIR, f"{slug}.md")

        content = f"""---
title: "{title}"
url: "{url}"
platform: "{record.get('platform', 'web')}"
category: "{category}"
tags:
{yaml_tags}
date: "{date_str}"
saved_via: "AVI Bot Telegram Vault"
---

# {title}

> **Source:** [{url}]({url})  
> **Category:** #{category.replace(' ', '')} | **Platform:** {record.get('platform', 'web')}  

## 📝 Executive Summary
{summary}

## 🏷️ Tags & Indexing
{md_hashtags}

---
*Generated by AVI Bot Obsidian Sync Engine*
"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return filepath
    except Exception as e:
        print(f"Obsidian note export error: {e}")
        return ""


def save_content(
    url: str,
    platform: str,
    title: str = None,
    caption: str = None,
    image_url: str = None,
    media_extraction_status: str = None,
    media_extraction_error: str = None,
    category: str = None,
    summary: str = None,
    summary_source: str = None,
    video_summary: str = None,
    video_summary_status: str = None,
    tags: str = None,
    user_phone: str = None
) -> int:
    """Save/update a content record in SQLite (idempotent), append to backup ledger, and write Obsidian note."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO saved_content (
                url, platform, title, caption, image_url,
                media_extraction_status, media_extraction_error,
                category, summary, summary_source, video_summary, video_summary_status, tags, user_phone
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                platform = COALESCE(excluded.platform, platform),
                title = COALESCE(excluded.title, title),
                caption = COALESCE(excluded.caption, caption),
                image_url = COALESCE(excluded.image_url, image_url),
                media_extraction_status = COALESCE(excluded.media_extraction_status, media_extraction_status),
                media_extraction_error = COALESCE(excluded.media_extraction_error, media_extraction_error),
                category = COALESCE(excluded.category, category),
                summary = COALESCE(excluded.summary, summary),
                summary_source = COALESCE(excluded.summary_source, summary_source),
                video_summary = COALESCE(excluded.video_summary, video_summary),
                video_summary_status = COALESCE(excluded.video_summary_status, video_summary_status),
                tags = COALESCE(excluded.tags, tags),
                user_phone = COALESCE(excluded.user_phone, user_phone),
                timestamp = CURRENT_TIMESTAMP
        ''', (
            url, platform, title, caption, image_url,
            media_extraction_status, media_extraction_error,
            category, summary, summary_source, video_summary, video_summary_status, tags, user_phone
        ))
        content_id = cursor.lastrowid or cursor.execute(
            'SELECT id FROM saved_content WHERE url = ?', (url,)
        ).fetchone()[0]

    record = {
        'id': content_id,
        'url': url,
        'platform': platform,
        'title': title,
        'caption': caption,
        'image_url': image_url,
        'media_extraction_status': media_extraction_status,
        'media_extraction_error': media_extraction_error,
        'category': category,
        'summary': summary,
        'summary_source': summary_source,
        'video_summary': video_summary,
        'video_summary_status': video_summary_status,
        'tags': tags,
        'user_phone': user_phone,
        'timestamp': datetime.now().isoformat()
    }
    append_to_backup_ledger(record)
    export_to_obsidian_note(record)

    return content_id


def get_all_content(
    limit: int = 100,
    offset: int = 0,
    platform: str = None,
    category: str = None,
    user_phone: str = None,
    search_query: str = None,
    collection: str = None
) -> List[Dict]:
    """Retrieve saved content records with optional filters and search."""
    query = 'SELECT * FROM saved_content WHERE 1=1'
    params = []

    if platform:
        query += ' AND platform = ?'
        params.append(platform)

    if category:
        query += ' AND category = ?'
        params.append(category)

    if user_phone:
        query += ' AND user_phone = ?'
        params.append(user_phone)

    if collection:
        query += ' AND collection = ?'
        params.append(collection)

    if search_query and search_query.strip():
        q = f'%{search_query.strip()}%'
        query += ' AND (title LIKE ? OR caption LIKE ? OR tags LIKE ? OR summary LIKE ? OR category LIKE ? OR url LIKE ? OR video_summary LIKE ?)'
        params.extend([q, q, q, q, q, q, q])

    query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_content_count(
    platform: str = None,
    category: str = None,
    user_phone: str = None,
    search_query: str = None,
    collection: str = None
) -> int:
    """Get count of saved content records matching filters and search query."""
    query = 'SELECT COUNT(*) FROM saved_content WHERE 1=1'
    params = []

    if platform:
        query += ' AND platform = ?'
        params.append(platform)

    if category:
        query += ' AND category = ?'
        params.append(category)

    if user_phone:
        query += ' AND user_phone = ?'
        params.append(user_phone)

    if collection:
        query += ' AND collection = ?'
        params.append(collection)

    if search_query and search_query.strip():
        q = f'%{search_query.strip()}%'
        query += ' AND (title LIKE ? OR caption LIKE ? OR tags LIKE ? OR summary LIKE ? OR category LIKE ? OR url LIKE ? OR video_summary LIKE ?)'
        params.extend([q, q, q, q, q, q, q])

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_content_by_id(content_id: int) -> Optional[Dict]:
    """Get content item by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM saved_content WHERE id = ?', (content_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_categories() -> List[str]:
    """Get list of all unique categories in saved content."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT category 
        FROM saved_content 
        WHERE category IS NOT NULL AND category != ''
        ORDER BY category
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_platforms() -> List[str]:
    """Get list of all unique platforms in saved content."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT platform 
        FROM saved_content 
        WHERE platform IS NOT NULL AND platform != ''
        ORDER BY platform
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_category_stats() -> Dict[str, int]:
    """Get breakdown of content counts by category."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT category, COUNT(*) as count 
        FROM saved_content 
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category
        ORDER BY count DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}


def get_stats() -> Dict:
    """Get comprehensive statistics for library dashboard."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM saved_content')
    total = cursor.fetchone()[0]

    cursor.execute('SELECT platform, COUNT(*) as count FROM saved_content GROUP BY platform')
    by_platform = {row[0]: row[1] for row in cursor.fetchall()}

    by_category = get_category_stats()

    cursor.execute("SELECT COUNT(*) FROM saved_content WHERE timestamp >= datetime('now', '-7 days')")
    recent = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(DISTINCT user_phone) 
        FROM saved_content 
        WHERE user_phone IS NOT NULL AND user_phone != ''
    ''')
    unique_users = cursor.fetchone()[0]
    conn.close()

    streak_data = get_streak_stats()

    return {
        'total': total,
        'by_platform': by_platform,
        'by_category': by_category,
        'categories': by_category,  # Alias for backwards compatibility
        'recent_7_days': recent,
        'unique_users': unique_users,
        'current_streak': streak_data['current_streak'],
        'total_this_week': streak_data['total_this_week'],
        'best_streak': streak_data['best_streak']
    }


def get_random_content(count: int = 5, exclude_id: int = None) -> List[Dict]:
    """Get random saved content items."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if exclude_id:
        cursor.execute('''
            SELECT * FROM saved_content WHERE id != ? ORDER BY RANDOM() LIMIT ?
        ''', (exclude_id, count))
    else:
        cursor.execute('SELECT * FROM saved_content ORDER BY RANDOM() LIMIT ?', (count,))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_random_content_by_category(count: int = 1, categories: List[str] = None) -> List[Dict]:
    """Get random content filtered by category."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if categories:
        placeholders = ','.join(['?'] * len(categories))
        cursor.execute(f'''
            SELECT * FROM saved_content 
            WHERE category IN ({placeholders})
            ORDER BY RANDOM() LIMIT ?
        ''', (*categories, count))
    else:
        cursor.execute('SELECT * FROM saved_content ORDER BY RANDOM() LIMIT ?', (count,))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_related_content(category: str, exclude_id: int = None, limit: int = 2) -> List[Dict]:
    """Get related content items in the same category."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if exclude_id:
        cursor.execute('''
            SELECT * FROM saved_content 
            WHERE category = ? AND id != ?
            ORDER BY RANDOM() LIMIT ?
        ''', (category, exclude_id, limit))
    else:
        cursor.execute('''
            SELECT * FROM saved_content WHERE category = ? ORDER BY RANDOM() LIMIT ?
        ''', (category, limit))

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_content_count_by_category(days: int = 7) -> Dict[str, int]:
    """Get content counts per category within N days."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT category, COUNT(*) as count 
        FROM saved_content 
        WHERE timestamp >= datetime('now', '-' || ? || ' days')
          AND category IS NOT NULL AND category != ''
        GROUP BY category ORDER BY count DESC
    ''', (days,))
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}


def get_total_content_count(days: int = 7) -> int:
    """Get total content count saved within N days."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM saved_content 
        WHERE timestamp >= datetime('now', '-' || ? || ' days')
    ''', (days,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def check_duplicate(url: str) -> Optional[Dict]:
    """Check if content URL already exists in database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM saved_content WHERE url = ?', (url,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_streak_stats(user_phone: str = None) -> Dict:
    """Calculate saving streak statistics."""
    from datetime import datetime as datetime_cls, timedelta

    conn = get_db_connection()
    cursor = conn.cursor()

    if user_phone:
        cursor.execute('''
            SELECT DATE(timestamp) as save_date 
            FROM saved_content 
            WHERE user_phone = ?
            GROUP BY DATE(timestamp)
            ORDER BY save_date DESC
        ''', (user_phone,))
    else:
        cursor.execute('''
            SELECT DATE(timestamp) as save_date 
            FROM saved_content 
            GROUP BY DATE(timestamp)
            ORDER BY save_date DESC
        ''')

    dates = [row[0] for row in cursor.fetchall()]

    if user_phone:
        cursor.execute('''
            SELECT COUNT(*) FROM saved_content 
            WHERE user_phone = ? AND timestamp >= datetime('now', '-7 days')
        ''', (user_phone,))
    else:
        cursor.execute("SELECT COUNT(*) FROM saved_content WHERE timestamp >= datetime('now', '-7 days')")

    result = cursor.fetchone()
    total_this_week = result[0] if result else 0
    conn.close()

    if not dates:
        return {'current_streak': 0, 'total_this_week': 0, 'best_streak': 0}

    today = datetime.now().date()
    date_set = set(dates)
    today_str = today.strftime('%Y-%m-%d')
    yesterday_str = (today - timedelta(days=1)).strftime('%Y-%m-%d')

    current_streak = 0
    check_date = None

    if today_str in date_set:
        current_streak = 1
        check_date = today - timedelta(days=1)
    elif yesterday_str in date_set:
        current_streak = 1
        check_date = today - timedelta(days=2)

    while check_date and check_date.strftime('%Y-%m-%d') in date_set:
        current_streak += 1
        check_date = check_date - timedelta(days=1)

    best_streak = 0
    if dates:
        date_objects = [datetime.strptime(d, '%Y-%m-%d').date() for d in dates]
        streak = 1
        prev_date = date_objects[0]
        for i in range(1, len(date_objects)):
            if (prev_date - date_objects[i]).days == 1:
                streak += 1
            else:
                best_streak = max(best_streak, streak)
                streak = 1
            prev_date = date_objects[i]
        best_streak = max(best_streak, streak)

    return {
        'current_streak': current_streak,
        'total_this_week': total_this_week,
        'best_streak': best_streak
    }


def parse_tags(tags_input) -> List[str]:
    """Parse tag input (string or list) into a deduplicated list of clean tags."""
    if not tags_input:
        return []
    if isinstance(tags_input, list):
        raw_tags = tags_input
    else:
        raw_tags = str(tags_input).replace(';', ',').replace(' ', ',').split(',')

    cleaned = []
    for tag in raw_tags:
        t = str(tag).strip().lstrip('#').lower()
        if t and len(t) >= 2 and t not in cleaned:
            cleaned.append(t)
    return cleaned


def get_content_by_tag(tag: str, limit: int = 20) -> List[Dict]:
    """Retrieve content items matching a specific tag."""
    conn = get_db_connection()
    cursor = conn.cursor()
    pattern = f'%{tag.lower()}%'
    cursor.execute('''
        SELECT * FROM saved_content
        WHERE LOWER(tags) LIKE ?
        ORDER BY timestamp DESC LIMIT ?
    ''', (pattern, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_popular_tags(limit: int = 20) -> List[Dict]:
    """Extract tag statistics across all saved items."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tags FROM saved_content WHERE tags IS NOT NULL AND tags != ''")
    rows = cursor.fetchall()
    conn.close()

    counts: Dict[str, int] = {}
    for row in rows:
        for tag in parse_tags(row[0]):
            counts[tag] = counts.get(tag, 0) + 1

    sorted_tags = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{'tag': tag, 'count': count} for tag, count in sorted_tags]


def search_content(
    query: str,
    limit: int = 20,
    offset: int = 0,
    platform: str = None,
    category: str = None,
    collection: str = None
) -> List[Dict]:
    """Search saved content with full filter and pagination support."""
    return get_all_content(
        limit=limit,
        offset=offset,
        platform=platform,
        category=category,
        search_query=query,
        collection=collection
    )


def delete_content(content_id: int) -> bool:
    """Delete content item by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM saved_content WHERE id = ?', (content_id,))
        return cursor.rowcount > 0


def update_content(
    content_id: int,
    title: str = None,
    caption: str = None,
    image_url: str = None,
    media_extraction_status: str = None,
    media_extraction_error: str = None,
    category: str = None,
    summary: str = None,
    summary_source: str = None,
    video_summary: str = None,
    video_summary_status: str = None,
    tags: str = None
) -> bool:
    """Update content item fields by ID."""
    updates = []
    params = []

    if title is not None:
        updates.append('title = ?')
        params.append(title)
    if caption is not None:
        updates.append('caption = ?')
        params.append(caption)
    if image_url is not None:
        updates.append('image_url = ?')
        params.append(image_url)
    if media_extraction_status is not None:
        updates.append('media_extraction_status = ?')
        params.append(media_extraction_status)
    if media_extraction_error is not None:
        updates.append('media_extraction_error = ?')
        params.append(media_extraction_error)
    if category is not None:
        updates.append('category = ?')
        params.append(category)
    if summary is not None:
        updates.append('summary = ?')
        params.append(summary)
    if summary_source is not None:
        updates.append('summary_source = ?')
        params.append(summary_source)
    if video_summary is not None:
        updates.append('video_summary = ?')
        params.append(video_summary)
    if video_summary_status is not None:
        updates.append('video_summary_status = ?')
        params.append(video_summary_status)
    if tags is not None:
        updates.append('tags = ?')
        params.append(tags)

    if not updates:
        return False

    params.append(content_id)
    query = f'UPDATE saved_content SET {", ".join(updates)} WHERE id = ?'
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.rowcount > 0


def init_collections_table():
    """Initialize collections table and column."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        try:
            cursor.execute('ALTER TABLE saved_content ADD COLUMN collection TEXT')
        except sqlite3.OperationalError:
            pass


def get_collections() -> List[str]:
    """Get all collections as a list of names."""
    init_collections_table()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM collections ORDER BY name')
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]


def create_collection(name: str):
    """Create a new collection."""
    init_collections_table()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO collections (name) VALUES (?)', (name,))


def assign_collection(content_id: int, collection_name: str):
    """Assign content item to a collection."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE saved_content SET collection = ? WHERE id = ?', (collection_name, content_id))


def delete_collection(name: str):
    """Delete a collection."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE saved_content SET collection = NULL WHERE collection = ?', (name,))
        cursor.execute('DELETE FROM collections WHERE name = ?', (name,))


def get_daily_save_counts(days: int = 365) -> Dict[str, int]:
    """Get daily save counts for user activity heatmap."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DATE(timestamp) as date, COUNT(*) as count
        FROM saved_content
        WHERE timestamp >= datetime('now', ?)
        GROUP BY DATE(timestamp)
        ORDER BY date
    ''', (f'-{days} days',))
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}


if __name__ == '__main__':
    init_db()
else:
    init_db()
