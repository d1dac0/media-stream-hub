import sqlite3
import os
import logging

# Set up logging
logger = logging.getLogger('media_streamer')

# Database file path
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_streamer.db')

def apply_migration_001(cursor):
    """Adds last_seen to users table and creates playback_state table."""
    try:
        # Add last_seen column to users table
        cursor.execute("ALTER TABLE users ADD COLUMN last_seen TIMESTAMP")
        logger.info("Successfully applied migration 001: Added last_seen to users table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logger.warning("Migration 001 already applied (last_seen column exists).")
        else:
            raise

    # Create playback_state table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS playback_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        media_path TEXT NOT NULL,
        position REAL NOT NULL,
        volume REAL NOT NULL,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        UNIQUE(user_id, media_path)
    )
    ''')
    logger.info("Successfully applied migration 001: Created playback_state table.")

def apply_migration_002(cursor):
    """Adds the media_metadata table for caching TMDB results."""
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS media_metadata (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT UNIQUE NOT NULL,
        poster_url TEXT,
        title TEXT,
        release_year INTEGER,
        media_type TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    logger.info("Successfully applied migration 002: Created media_metadata table.")

def run_migrations():
    """Applies all pending database migrations."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Create migrations table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS migrations (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Check if migration 001 has been applied
        cursor.execute("SELECT 1 FROM migrations WHERE name = '001_add_last_seen_and_playback_state'")
        if cursor.fetchone() is None:
            apply_migration_001(cursor)
            cursor.execute("INSERT INTO migrations (name) VALUES ('001_add_last_seen_and_playback_state')")
            logger.info("Migration 001 applied successfully.")
        
        # Check if migration 002 has been applied
        cursor.execute("SELECT 1 FROM migrations WHERE name = '002_add_metadata_cache_table'")
        if cursor.fetchone() is None:
            apply_migration_002(cursor)
            cursor.execute("INSERT INTO migrations (name) VALUES ('002_add_metadata_cache_table')")
            logger.info("Migration 002 applied successfully.")
        else:
            logger.info("Migration 002 already applied, skipping.")
            
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    run_migrations()
    print("Database migrations completed.")
