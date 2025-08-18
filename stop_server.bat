@echo off
echo Stopping Media Streamer server...

set "port=8080"
set "pid="

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%port% ^| findstr "LISTENING"') do (
    set "pid=%%a"
    goto :found_pid
)

:found_pid
if defined pid (
    echo Server process found with PID: %pid%
    taskkill /F /PID %pid%
    echo Server stopped successfully.
) else (
    echo Server does not appear to be running.
)

pause
