import os
import secrets
import bcrypt
from waitress import serve
from app import app, logger
from database import init_db

# Set default environment variables if not already set
if not os.environ.get('SECRET_KEY'):
    # Generate a random secret key if not provided
    secret_key = secrets.token_hex(32)
    os.environ['SECRET_KEY'] = secret_key
    print(f"WARNING: Using a randomly generated SECRET_KEY. For persistent sessions, set this as an environment variable.")
    logger.warning(f"Using randomly generated SECRET_KEY. Set this in environment for persistent sessions.")

# Initialize the database and create admin user if needed
print("Initializing database...")
init_db()
print("Database initialized successfully.")

# Set debug mode to False for production
os.environ['DEBUG_MODE'] = 'False'

# Start the server
print("Starting Media Streamer server...")
print("\nServer is running at http://localhost:8080")
print("Press Ctrl+C to stop the server")

# Serve the application with Waitress
serve(app, host='0.0.0.0', port=8080)
