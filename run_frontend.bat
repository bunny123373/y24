@echo off
REM Antigravity Media Downloader - Frontend Launcher
REM Starts the Vite dev server on port 5173 and automatically opens the browser.
echo Starting Vite Frontend on http://localhost:5173 ...
start http://localhost:5173
npm --prefix frontend run dev
