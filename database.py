import os
import sqlite3
import bcrypt
import secrets
import logging

# Set up logging
logger = logging.getLogger('media_streamer')

# Database file path
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media_streamer.db')

def get_db_connection():
    """Create a database connection and return it"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with required tables"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create users table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Check if default admin user exists
        admin_user = get_user_by_username('admin')
        
        if not admin_user:
            # Generate a random password for admin if not set in environment
            admin_password = os.environ.get('ADMIN_PASSWORD')
            if not admin_password:
                admin_password = secrets.token_urlsafe(16)
                logger.warning(f"Generated a random admin password: {admin_password}. Set ADMIN_PASSWORD in your .env file for a persistent password.")

            # Hash the password
            salt = bcrypt.gensalt()
            hashed_password = bcrypt.hashpw(admin_password.encode('utf-8'), salt)
            
            # Insert admin user
            cursor.execute(
                "INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
                ('admin', hashed_password.decode('utf-8'), True)
            )
            print(f"Created default admin user with password: {admin_password}")
            logger.info("Created default admin user")
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        if 'conn' in locals():
            conn.close()
        return False

def get_user_by_username(username):
    """Fetches a user by their username."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"Database error while fetching user '{username}': {e}")
        return None

def get_user_by_id(user_id):
    """Fetches a user by their ID."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"Database error while fetching user with ID {user_id}: {e}")
        return None

def update_user_last_seen(user_id):
    """Updates the last_seen timestamp for a user."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error updating last_seen for user {user_id}: {e}")

def verify_user(username, password):
    """Verify user credentials"""
    if not username or not password:
        logger.warning("Attempt to verify user with missing credentials")
        return None

    try:
        user = get_user_by_username(username)
        if not user:
            logger.warning(f"Login attempt with non-existent username: {username}")
            return None

        # Verify password
        password_bytes = password.encode('utf-8')
        stored_hash = user['password'].encode('utf-8')
        
        if bcrypt.checkpw(password_bytes, stored_hash):
            logger.info(f"Successful password verification for user: {username}")
            return dict(user)
        else:
            logger.warning(f"Failed password verification for user: {username}")
            return None
            
    except Exception as e:
        logger.error(f"Database error during user verification: {e}")
        return None

def add_user(username, password, is_admin=False):
    """Add a new user to the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            conn.close()
            logger.warning(f"Attempted to create duplicate user: {username}")
            return False, "User already exists"
        
        # Hash the password
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
        
        # Insert new user
        cursor.execute(
            "INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
            (username, hashed_password.decode('utf-8'), is_admin)
        )
        conn.commit()
        conn.close()
        
        logger.info(f"Successfully created new user: {username}")
        return True, "User created successfully"
        
    except Exception as e:
        logger.error(f"Error adding user: {e}")
        if 'conn' in locals():
            conn.close()
        return False, "Error creating user"

def save_playback_state(user_id, media_path, position, volume):
    """Saves or updates the playback state for a user and media file."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO playback_state (user_id, media_path, position, volume, last_updated)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, media_path) DO UPDATE SET
                position = excluded.position,
                volume = excluded.volume,
                last_updated = excluded.last_updated
        """, (user_id, media_path, position, volume))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error saving playback state for user {user_id}: {e}")

def load_playback_state(user_id):
    """Loads all playback states for a given user."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT media_path, position, volume FROM playback_state WHERE user_id = ?", (user_id,))
        states = cursor.fetchall()
        conn.close()
        return {row['media_path']: {'position': row['position'], 'volume': row['volume']} for row in states}
    except Exception as e:
        logger.error(f"Error loading playback state for user {user_id}: {e}")
        return {}

def get_all_users():
    """Get all users from the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, is_admin, created_at FROM users")
        users = cursor.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        return [dict(user) for user in users]
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return []

def delete_user(user_id):
    """Delete a user from the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return False, "User not found"
        
        # Prevent deleting the last admin user
        if user['is_admin']:
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_admin = 1")
            admin_count = cursor.fetchone()['count']
            
            if admin_count <= 1:
                conn.close()
                return False, "Cannot delete the last admin user"
        
        # Delete the user
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"Deleted user with ID: {user_id}")
        return True, "User deleted successfully"
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        return False, str(e)

def change_password(username, new_password):
    """Change a user's password"""
    try:
        # Hash the new password
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), salt)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return False, "User not found"
        
        # Update the password
        cursor.execute(
            "UPDATE users SET password = ? WHERE username = ?",
            (hashed_password.decode('utf-8'), username)
        )
        conn.commit()
        conn.close()
        
        logger.info(f"Changed password for user: {username}")
        return True, "Password changed successfully"
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        return False, str(e)

# Initialize the database when this module is imported
if not os.path.exists(DB_PATH):
    init_db()
