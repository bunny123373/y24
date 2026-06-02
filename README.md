# y24 - Fullstack Media Downloader

A premium, decoupled media downloader application consisting of a **Python FastAPI backend** and a **Vite + Vanilla JS/CSS frontend**. It uses `yt-dlp` to download media and automatically streams completed downloads directly to your local browser downloads folder.

## Key Features
* 🌟 **Decoupled Architecture**: High-performance FastAPI backend connected with a responsive Vite dev server.
* 🎨 **Glassmorphic UI/UX**: Premium dark mode visual dashboard with micro-animations.
* ⚡ **Server-Sent Events (SSE)**: Real-time progress bars, speed, and time estimations streamed dynamically.
* 🖼️ **Thumbnail & Info Previews**: Instantly extracts metadata and proxies images to bypass client-side DNS/firewall restrictions.
* 🔒 **Secure Auto-Downloads**: Directly triggers browser download prompts when background compiles finish on the server, with directory traversal safeguards.
* 🔀 **Format Selectors**: Dynamic selectors for choosing between MP4 (MKV merge format) and high-quality MP3 audio extractions.
* 🛑 **Concurrency Lock**: Prevents file clashes by blocking overlapping duplicate downloads of the same URL.

---

## Project Structure
```text
y24/
├── backend/                  # FastAPI Application
│   ├── config.py             # Server parameters and config.json loader
│   ├── downloader.py         # yt-dlp core downloader wrapper
│   ├── main.py               # REST API endpoints, SSE stream, and static proxy
│   └── requirements.txt      # Python dependencies
│
├── frontend/                 # Vite + HTML/CSS/JS Application
│   ├── src/
│   │   ├── main.js           # Event listeners, SSE hooks, and Auto-Download trigger
│   │   └── style.css         # Glassmorphism design system
│   ├── public/               # Static favicons
│   ├── index.html            # Core Single Page App grid layout
│   └── vite.config.js        # Vite port configuration & API proxy
│
├── run_backend.bat           # Run FastAPI server on port 5000
├── run_frontend.bat          # Run Vite client on port 5173
├── run_fullstack.bat         # Run both backend and frontend servers
└── .gitignore                # File exclusions for version control
```

---

## Quick Start

### 1. Initialize Virtual Environment
```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 2. Install Frontend dependencies
```bash
cd frontend
npm install
cd ..
```

### 3. Run the application
Run the launcher script in your shell to start both servers and auto-open the browser:
```cmd
.\run_fullstack.bat
```
Alternatively, launch them separately:
* Run backend: `.\run_backend.bat`
* Run frontend: `.\run_frontend.bat`
