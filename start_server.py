import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from waitress import serve
from app import app, logger
from database import init_db
from migrations import run_migrations

# Set default environment variables if not already set
if 'SECRET_KEY' not in os.environ:
    # Generate a random secret key if not provided
    import secrets
    secret_key = secrets.token_hex(32)
    os.environ['SECRET_KEY'] = secret_key
    logger.warning("Using randomly generated SECRET_KEY. For persistent sessions, set this as an environment variable in a .env file.")

# Run database migrations
print("Running database migrations...")
run_migrations()
print("Migrations completed.")

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
