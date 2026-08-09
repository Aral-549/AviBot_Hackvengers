#!/usr/bin/env python3
"""
One-time migration: deduplicate rows in saved_content and add UNIQUE constraint on url.

Run once before deploying the fix:
    python3 migrate_dedup.py

What it does:
1. Finds all URLs with more than one row
2. Keeps the row with the highest id (most recent), deletes the rest
3. Creates a UNIQUE index on url (idempotent — uses IF NOT EXISTS)

Safe to re-run: the dedup query only touches duplicates, and the index
creation is IF NOT EXISTS.
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), 'social_saver.db')


def migrate():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Step 1: Find duplicate URLs
    cursor.execute('''
        SELECT url, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
        FROM saved_content
        GROUP BY url
        HAVING cnt > 1
    ''')
    duplicates = cursor.fetchall()

    total_deleted = 0
    for row in duplicates:
        url = row['url']
        ids = [int(x) for x in row['ids'].split(',')]
        keep_id = max(ids)  # keep newest
        delete_ids = [i for i in ids if i != keep_id]

        if delete_ids:
            placeholders = ','.join('?' * len(delete_ids))
            cursor.execute(
                f'DELETE FROM saved_content WHERE id IN ({placeholders})',
                delete_ids
            )
            total_deleted += len(delete_ids)
            print(f"  URL: {url[:60]}... — kept id={keep_id}, deleted ids={delete_ids}")

    if total_deleted:
        print(f"\nDeleted {total_deleted} duplicate row(s).")
    else:
        print("No duplicate rows found.")

    # Step 2: Add UNIQUE index (idempotent)
    try:
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_url_unique ON saved_content(url)')
        print("UNIQUE index on url created (or already exists).")
    except sqlite3.IntegrityError as e:
        print(f"Cannot create UNIQUE index — duplicates still exist: {e}")
        conn.rollback()
        conn.close()
        return

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == '__main__':
    migrate()
