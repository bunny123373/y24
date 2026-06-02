@echo off
REM Antigravity Fullstack Media Downloader Launcher
REM Launches FastAPI backend, Vite dev server, and opens browser.

echo Starting Antigravity Downloader Backend...
start "Antigravity Backend" .\venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 5000 --reload

echo Starting Antigravity Downloader Frontend...
start "Antigravity Frontend" /D frontend npm run dev

echo Opening browser...
ping 127.0.0.1 -n 4 >nul
start http://localhost:5173
