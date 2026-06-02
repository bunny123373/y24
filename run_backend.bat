@echo off
REM Antigravity Media Downloader - Backend Launcher
REM Starts the FastAPI backend server on port 5000.
echo Starting FastAPI Backend on http://127.0.0.1:5000 ...
.\venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 5000 --reload
