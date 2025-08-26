import os
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

# Load environment variables from .env file at the very top
load_dotenv()

from app import get_media_metadata, SUPPORTED_MEDIA_TYPES, MEDIA_FOLDER
from database import get_cached_metadata, remove_cached_metadata

logger = logging.getLogger('media_streamer_watcher')

class MediaCacheHandler(FileSystemEventHandler):
    """Handles file system events to keep the metadata cache up to date."""

    def process(self, event_path):
        """Processes a file creation or modification event."""
        filename = os.path.basename(event_path)
        ext = os.path.splitext(filename)[1].lower()
        
        if ext in SUPPORTED_MEDIA_TYPES:
            logger.info(f"Change detected for: {filename}. Updating cache...")
            get_media_metadata(filename) # This will fetch and cache it

    def on_created(self, event):
        if not event.is_directory:
            self.process(event.src_path)

    def on_modified(self, event):
        # Sometimes new files trigger modified first
        if not event.is_directory:
            self.process(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            filename = os.path.basename(event.src_path)
            logger.info(f"Deletion detected for: {filename}. Removing from cache.")
            remove_cached_metadata(filename)

def initial_cache_scan():
    """Scans the media folder on startup to cache any missing metadata."""
    logger.info("Performing initial scan of media folder to build cache...")
    scanned_files = 0
    cached_files = 0
    for root, _, files in os.walk(MEDIA_FOLDER):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in SUPPORTED_MEDIA_TYPES:
                scanned_files += 1
                if not get_cached_metadata(filename):
                    logger.info(f"'{filename}' not found in cache. Fetching from TMDB...")
                    get_media_metadata(filename)
                    cached_files += 1
    
    logger.info(f"Initial scan complete. Scanned {scanned_files} files, cached {cached_files} new files.")

def start_watcher():
    """Starts the file system watcher."""
    if not os.path.exists(MEDIA_FOLDER):
        logger.error(f"Media folder not found: {MEDIA_FOLDER}. Watcher not started.")
        return

    logger.info(f"Starting file system watcher for: {MEDIA_FOLDER}")
    event_handler = MediaCacheHandler()
    observer = Observer()
    observer.schedule(event_handler, MEDIA_FOLDER, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    initial_cache_scan()
    start_watcher()
