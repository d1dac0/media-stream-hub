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
from database import init_db, verify_user, add_user, get_all_users, delete_user, change_password

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
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1)
)
csrf = CSRFProtect(app)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

# Get media folder from environment variable or use default
MEDIA_FOLDER = os.environ.get('MEDIA_FOLDER', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media'))
# Ensure media folder exists
os.makedirs(MEDIA_FOLDER, exist_ok=True)

# Set restrictive permissions on media folder
try:
    os.chmod(MEDIA_FOLDER, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
except Exception as e:
    logger.warning(f"Could not set permissions on media folder: {e}")

# File to store playback state
PLAYBACK_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'playback_state.json')

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
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; img-src 'self' data: https://images.unsplash.com; font-src 'self' https://cdnjs.cloudflare.com; media-src 'self'"
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Cache-Control'] = 'no-store, max-age=0'
    return response

# Load playback state from file
def load_playback_state():
    """Load the saved playback state from file."""
    try:
        if os.path.exists(PLAYBACK_STATE_FILE):
            with open(PLAYBACK_STATE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading playback state: {e}")
    return {}

# Save playback state to file
def save_playback_state(state):
    """Save the current playback state to file."""
    try:
        # Use atomic write to prevent corruption
        temp_file = f"{PLAYBACK_STATE_FILE}.tmp"
        with open(temp_file, 'w') as f:
            json.dump(state, f)
        os.replace(temp_file, PLAYBACK_STATE_FILE)
        
        # Set restrictive permissions
        os.chmod(PLAYBACK_STATE_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except Exception as e:
        logger.error(f"Error saving playback state: {e}")

# Routes
@app.route('/')
def index():
    """Main page route."""
    return render_template('index.html')

@app.route('/api/media')
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
def api_playback_state():
    """API endpoint to get or update playback state."""
    try:
        if request.method == 'POST':
            data = request.get_json()
            if not data or not isinstance(data, dict):
                return jsonify({"error": "Invalid data"}), 400
            
            # Load current state
            state = load_playback_state()
            
            # Update state with new data
            file_path = data.get('path')
            if file_path:
                state[file_path] = {
                    'position': data.get('position', 0),
                    'volume': data.get('volume', 1.0),
                    'lastPlayed': time.time()
                }
                
                # Save updated state
                save_playback_state(state)
                return jsonify({"status": "success"})
            else:
                return jsonify({"error": "Missing file path"}), 400
        else:
            # Return all saved states
            return jsonify(load_playback_state())
            
    except Exception as e:
        logger.error(f"Error handling playback state: {e}")
        return jsonify({"error": "Server error"}), 500

@app.route('/media/<path:filename>')
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=app.config['DEBUG'])
