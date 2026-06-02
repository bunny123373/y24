@echo off
REM Antigravity Web Downloader Server Launcher
REM Opens the browser and launches the web GUI.
start http://127.0.0.1:5000
.\venv\Scripts\python web_server.py
