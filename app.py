import os
import re
import time
import stat
import json
import logging
from datetime import timedelta, datetime
from flask import Flask, render_template, send_from_directory, jsonify, request, abort, session, make_response, redirect, url_for, flash
from pathlib import Path
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import bcrypt
from logging.handlers import RotatingFileHandler
from database import (
    init_db, verify_user, add_user, get_all_users, delete_user, 
    change_password, get_user_by_id, update_user_last_seen,
    save_playback_state, load_playback_state
)

# Set up logging
log_file = os.environ.get('LOG_FILE', 'media_streamer.log')
logger = logging.getLogger('media_streamer')
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(log_file, maxBytes=10485760, backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Initialize the database
init_db()

# Set up Flask app
app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'default-secret-key'),
    DEBUG=os.environ.get('DEBUG_MODE', 'False').lower() == 'true',
    SESSION_COOKIE_SECURE=os.environ.get('DEBUG_MODE', 'False').lower() != 'true',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
    WTF_CSRF_TIME_LIMIT=None
)

# ---- START DEBUG PRINT ----
print(f"--- CONFIGURATION --- DEBUG_MODE: {app.config['DEBUG']}")
print(f"--- CONFIGURATION --- SESSION_COOKIE_SECURE: {app.config['SESSION_COOKIE_SECURE']}")
# ---- END DEBUG PRINT ----

csrf = CSRFProtect(app)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["2000 per day", "500 per hour"]
)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(error='User not authenticated'), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def before_request_tasks():
    """Tasks to run before each request."""
    # Renew session on activity
    session.permanent = True
    app.permanent_session_lifetime = timedelta(hours=1)
    
    # Update last seen for logged-in users
    if 'user_id' in session:
        update_user_last_seen(session['user_id'])

# Get media folder from environment variable or use default
MEDIA_FOLDER = os.environ.get('MEDIA_FOLDER', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media'))
# Ensure media folder exists
os.makedirs(MEDIA_FOLDER, exist_ok=True)

# Set restrictive permissions on media folder
try:
    os.chmod(MEDIA_FOLDER, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
except Exception as e:
    logger.warning(f"Could not set permissions on media folder: {e}")

# Supported file types
SUPPORTED_VIDEO_TYPES = ['.mp4', '.webm', '.mkv', '.avi', '.mov']
SUPPORTED_AUDIO_TYPES = ['.mp3', '.wav', '.ogg', '.flac', '.aac']
SUPPORTED_MEDIA_TYPES = SUPPORTED_VIDEO_TYPES + SUPPORTED_AUDIO_TYPES

# Security headers
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' https://cdnjs.cloudflare.com https://cdn.plyr.io; "
        "style-src 'self' https://cdnjs.cloudflare.com https://cdn.plyr.io; "
        "img-src 'self' data: https://cdn.plyr.io; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "connect-src 'self' https://cdn.plyr.io;"
    )
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response
    
# Remove file-based playback state functions
# No longer needed as this is handled in the database via API

# Routes
@app.route('/')
@login_required
def index():
    """Main page route."""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page for users."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = verify_user(username, password)
        if user:
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            session['user_ip'] = request.remote_addr
            
            logger.info(f"User '{username}' logged in successfully.")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password.", "danger")
            logger.warning(f"Failed login attempt for username: '{username}'.")
            
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    """Logs out the current user."""
    logger.info(f"User '{session.get('username')}' logged out.")
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))
    
@app.route('/admin')
@login_required
@admin_required
def admin_panel():
    """Admin panel to manage users."""
    users = get_all_users()
    return render_template('admin.html', users=users)

# Health check route
@app.route('/health')
def health_check():
    """Health check endpoint for monitoring."""
    return "OK", 200

@app.route('/api/media')
@login_required
def get_media_files():
    """API endpoint to get all media files."""
    try:
        media_files = []
        for root, _, files in os.walk(MEDIA_FOLDER):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, MEDIA_FOLDER)
                ext = os.path.splitext(file)[1].lower()
                
                if ext in SUPPORTED_MEDIA_TYPES:
                    # Get file info
                    file_stat = os.stat(file_path)
                    file_info = {
                        'name': file,
                        'path': rel_path.replace('\\', '/'),  # Normalize path for web
                        'size': file_stat.st_size,
                        'modified': file_stat.st_mtime,
                        'type': 'video' if ext in SUPPORTED_VIDEO_TYPES else 'audio'
                    }
                    media_files.append(file_info)
        
        return jsonify({'files': media_files})  # Wrap in 'files' object
    except Exception as e:
        logger.error(f"Error getting media files: {e}")
        return jsonify({"error": "Failed to get media files"}), 500

@app.route('/api/playback-state', methods=['GET', 'POST'])
@login_required
def api_playback_state():
    """API endpoint to get or update playback state."""
    user_id = session['user_id']
    
    try:
        if request.method == 'POST':
            data = request.get_json()
            if not data or 'path' not in data or 'position' not in data:
                return jsonify({"error": "Invalid data"}), 400
            
            save_playback_state(
                user_id,
                data['path'],
                data['position'],
                data.get('volume', 1.0)
            )
            return jsonify({"status": "success"})
        else:
            return jsonify(load_playback_state(user_id))
            
    except Exception as e:
        logger.error(f"Error handling playback state for user {user_id}: {e}")
        return jsonify({"error": "Server error"}), 500

@app.route('/media/<path:filename>')
@login_required
def serve_media(filename):
    """Serve media files securely."""
    try:
        # Normalize the path to prevent directory traversal
        safe_path = os.path.normpath(filename).replace('\\', '/')
        if '..' in safe_path:
            abort(403)
        
        # Check if file exists and has supported extension
        file_path = os.path.join(MEDIA_FOLDER, safe_path)
        if not os.path.isfile(file_path):
            abort(404)
            
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in SUPPORTED_MEDIA_TYPES:
            abort(403)
        
        # Get file size for range requests
        file_size = os.path.getsize(file_path)
        
        # Handle range requests
        range_header = request.headers.get('Range')
        
        if range_header:
            byte_range = range_header.replace('bytes=', '').split('-')
            start = int(byte_range[0])
            end = int(byte_range[1]) if byte_range[1] else file_size - 1
            
            if start >= file_size:
                abort(416)  # Range Not Satisfiable
                
            # Create response with range
            response = make_response()
            response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Content-Length'] = str(end - start + 1)
            response.status_code = 206  # Partial Content
            
            # Set appropriate content type
            if ext in SUPPORTED_VIDEO_TYPES:
                response.headers['Content-Type'] = 'video/mp4'  # Default to MP4
            else:
                response.headers['Content-Type'] = 'audio/mpeg'  # Default to MP3
            
            # Stream the file
            def generate():
                with open(file_path, 'rb') as f:
                    f.seek(start)
                    remaining = end - start + 1
                    chunk_size = 8192
                    
                    while remaining:
                        chunk = f.read(min(chunk_size, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk
            
            response.response = generate()
            return response
        
        # For non-range requests, use send_from_directory
        return send_from_directory(MEDIA_FOLDER, safe_path)
        
    except Exception as e:
        logger.error(f"Error serving media file: {e}")
        abort(500)

@app.route('/api/settings', methods=['POST'])
@login_required
@admin_required
def update_settings():
    """Update application settings."""
    data = request.get_json()
    if not data or 'media_folder' not in data:
        return jsonify({"error": "Invalid data"}), 400
    
    new_media_folder = data['media_folder']
    
    # Very basic validation - in a real app, you'd want more robust checks
    if not os.path.isdir(new_media_folder):
        return jsonify({"error": "Media folder not found"}), 400
        
    global MEDIA_FOLDER
    MEDIA_FOLDER = new_media_folder
    
    # Here you might want to save this to a persistent config file or env var
    # For now, it's just in memory
    logger.info(f"Admin '{session['username']}' updated MEDIA_FOLDER to: {new_media_folder}")
    
    return jsonify({"status": "success"})
    
# Error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"error": "Not found"}), 404
    return render_template('error.html', error="Page not found"), 404

@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors."""
    logger.error(f"Server error: {error}")
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"error": "Server error"}), 500
    return render_template('error.html', error="Server error"), 500

@app.errorhandler(429)
def too_many_requests(error):
    """Handle 429 errors (rate limiting)."""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"error": "Too many requests"}), 429
    return render_template('error.html', error="Too many requests"), 429

@app.errorhandler(403)
def forbidden(error):
    """Handle 403 Forbidden errors."""
    return render_template('error.html', error="You don't have permission to access this page."), 403

@app.route('/api/users', methods=['POST'])
@login_required
@admin_required
def create_user():
    """Create a new user."""
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "Missing username or password"}), 400
    
    success, message = add_user(
        data['username'],
        data['password'],
        data.get('is_admin', False)
    )
    
    if success:
        return jsonify({"status": "success", "message": message})
    else:
        return jsonify({"error": message}), 400

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def remove_user(user_id):
    """Delete a user."""
    if user_id == session['user_id']:
        return jsonify({"error": "Cannot delete yourself"}), 400
        
    success, message = delete_user(user_id)
    if success:
        return jsonify({"status": "success", "message": message})
    else:
        return jsonify({"error": message}), 400

@app.route('/api/users/change-password', methods=['POST'])
@login_required
def change_user_password():
    """Change the current user's password."""
    data = request.get_json()
    if not data or 'current_password' not in data or 'new_password' not in data:
        return jsonify({"error": "Missing required fields"}), 400
        
    user = get_user_by_id(session['user_id'])
    
    # Verify current password
    if not bcrypt.checkpw(data['current_password'].encode('utf-8'), user['password'].encode('utf-8')):
        return jsonify({"error": "Incorrect current password"}), 400
    
    # Change password
    success, message = change_password(user['username'], data['new_password'])
    
    if success:
        return jsonify({"status": "success", "message": message})
    else:
        return jsonify({"error": message}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=app.config['DEBUG'])
