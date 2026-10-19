@echo off
title DEBUNK.IT - Cloudflare Tunnel Launcher
color 0B

echo ========================================================
echo         DEBUNK.IT - Cloudflare Tunnel Launcher
echo ========================================================
echo.

:: 1. Check virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo [!] Virtual environment not found! Please create it or run pip install.
    pause
    exit /b 1
)

:: 2. Check cloudflared binary
if not exist "tools\cloudflared.exe" (
    echo [!] tools\cloudflared.exe not found!
    pause
    exit /b 1
)

echo [*] Starting DEBUNK.IT production WSGI server (Waitress) on port 5000...
start "DEBUNK.IT Server (Waitress)" .venv\Scripts\python.exe serve.py

:: Wait 2 seconds for server to bind
timeout /t 2 /nobreak >nul

echo [*] Connecting Cloudflare Tunnel to http://127.0.0.1:5000...
echo.
echo ========================================================
echo Look for your public URL below (ending in .trycloudflare.com):
echo ========================================================
echo.

tools\cloudflared.exe tunnel --url http://127.0.0.1:5000

pause
