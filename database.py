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
        cursor.execute("SELECT * FROM users WHERE username = 'admin'")
        admin_exists = cursor.fetchone()
        
        if not admin_exists:
            # Generate a random password for admin if not set in environment
            admin_password = os.environ.get('ADMIN_PASSWORD', 'crUA0XSWYB9gTmq6')
            
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

def verify_user(username, password):
    """Verify user credentials"""
    if not username or not password:
        logger.warning("Attempt to verify user with missing credentials")
        return False

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get user by username
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        
        if not user:
            logger.warning(f"Login attempt with non-existent username: {username}")
            conn.close()
            return False
        
        # Verify password
        try:
            # Convert password to bytes for bcrypt
            password_bytes = password.encode('utf-8')
            stored_hash = user['password'].encode('utf-8')
            
            # Verify the password
            is_valid = bcrypt.checkpw(password_bytes, stored_hash)
            
            if is_valid:
                logger.info(f"Successful password verification for user: {username}")
            else:
                logger.warning(f"Failed password verification for user: {username}")
            
            conn.close()
            return is_valid
                
        except Exception as e:
            logger.error(f"Password verification error for user {username}: {e}")
            logger.error("Password bytes length: %d", len(password_bytes))
            logger.error("Stored hash length: %d", len(stored_hash))
            conn.close()
            return False
            
    except Exception as e:
        logger.error(f"Database error during user verification: {e}")
        if 'conn' in locals():
            conn.close()
        return False

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
