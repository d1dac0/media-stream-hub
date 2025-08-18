@echo off
echo Restarting Media Streamer server...
echo.

echo Stopping the current server instance (if it's running)...
call stop_server.bat
echo.

echo Starting the new server instance...
call start_server.bat
echo.

echo Restart process completed. The server is now running in the background.
