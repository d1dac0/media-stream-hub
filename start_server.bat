@echo off
echo Starting Media Streamer components...

echo Starting Web Server in background...
start "WebServer" /min pythonw start_server.py

echo Starting File Watcher in background...
start "FileWatcher" /min pythonw file_watcher.py

echo All components are running.
