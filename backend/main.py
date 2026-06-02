import os
import sys

# Inject Deno path to environment variables for Render compatibility
for path in ["/opt/render/.deno/bin", os.path.expanduser("~/.deno/bin")]:
    if os.path.exists(path):
        os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")

# Add backend directory to Python path to ensure clean imports when run from root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uuid
import json
import asyncio
import threading
from typing import Dict, Any
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.responses import RedirectResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

# Reconfigure standard streams to UTF-8 on Windows to prevent UnicodeEncodeError
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import config
from downloader import YtdlpDownloader

app = FastAPI(
    title="Antigravity Downloader API",
    description="REST & SSE APIs managing yt-dlp media downloads",
    version="1.0.0"
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # During development, allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread-safe dictionary tracking active download tasks
active_downloads = {}
downloads_lock = threading.Lock()

def make_progress_hook(download_id: str):
    """Creates a yt-dlp progress hook tied to a specific download job ID."""
    def hook(d):
        with downloads_lock:
            if download_id not in active_downloads:
                return

            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                percent = (downloaded / total * 100) if total > 0 else 0
                
                # Format download speed
                speed_bytes = d.get('speed')
                speed_str = "0 B/s"
                if speed_bytes:
                    if speed_bytes > 1024 * 1024:
                        speed_str = f"{speed_bytes / (1024 * 1024):.1f} MB/s"
                    elif speed_bytes > 1024:
                        speed_str = f"{speed_bytes / 1024:.1f} KB/s"
                    else:
                        speed_str = f"{speed_bytes} B/s"

                # Format remaining time
                eta_val = d.get('eta')
                eta_str = "Unknown"
                if eta_val is not None:
                    m = eta_val // 60
                    s = eta_val % 60
                    eta_str = f"{m:02d}:{s:02d}"

                active_downloads[download_id].update({
                    "status": "downloading",
                    "progress": round(percent, 1),
                    "speed": speed_str,
                    "eta": eta_str
                })
            elif d['status'] == 'finished':
                # Reached 100%, now post-processing (FFmpeg, thumbnails, etc.)
                active_downloads[download_id].update({
                    "status": "processing",
                    "progress": 100,
                    "speed": "0 B/s",
                    "eta": "Processing..."
                })
    return hook

def find_downloaded_filename(download_dir: str, title: str, dl_type: str, quality: str) -> str:
    """Scans the download directory to find the newly completed file name based on modified time."""
    if not os.path.exists(download_dir):
        return None
        
    files = []
    for name in os.listdir(download_dir):
        file_path = os.path.join(download_dir, name)
        if os.path.isfile(file_path):
            files.append((name, os.path.getmtime(file_path)))
            
    # Sort files by newest modified time
    files.sort(key=lambda x: x[1], reverse=True)
    if files:
        for name, _ in files:
            _, ext = os.path.splitext(name)
            ext = ext.lower()
            if dl_type == "audio" and ext in [".mp3", ".m4a", ".flac", ".ogg", ".wav"]:
                return name
            if dl_type == "video" and ext in [".mkv", ".mp4", ".webm"]:
                return name
        return files[0][0]
    return None

def download_worker(download_id: str, url: str, dl_type: str, quality: str):
    """Background worker that handles fetching metadata and downloading media."""
    try:
        with downloads_lock:
            active_downloads[download_id] = {
                "id": download_id,
                "url": url,
                "title": "Fetching metadata...",
                "status": "pending",
                "progress": 0,
                "speed": "0 B/s",
                "eta": "Connecting...",
                "type": dl_type,
                "filename": None,
                "error": None
            }

        # 1. Fetch info to extract title
        current_config = config.load_config()
        downloader = YtdlpDownloader(current_config)
        info = downloader.get_info(url)
        
        with downloads_lock:
            if info:
                title = info.get("title", "Unknown Video")
                active_downloads[download_id]["title"] = title
            else:
                active_downloads[download_id]["title"] = url

        # 2. Set up download with the dynamic progress hook
        hook = make_progress_hook(download_id)
        downloader_with_hook = YtdlpDownloader(current_config, progress_hook=hook)

        if dl_type == "audio":
            downloader_with_hook.download_audio(url, audio_format=quality)
        else:
            downloader_with_hook.download_video(url, resolution=quality)

        # Resolve target filename from downloads directory
        download_dir = current_config.get("download_dir", "downloads")
        if not os.path.isabs(download_dir):
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.dirname(backend_dir)
            download_dir = os.path.join(root_dir, download_dir)
            
        filename = find_downloaded_filename(download_dir, active_downloads[download_id]["title"], dl_type, quality)

        with downloads_lock:
            active_downloads[download_id].update({
                "status": "finished",
                "progress": 100,
                "eta": "Completed",
                "filename": filename
            })
    except Exception as e:
        with downloads_lock:
            active_downloads[download_id].update({
                "status": "failed",
                "error": str(e),
                "eta": "Failed"
            })

@app.get("/")
def read_root():
    """Welcome index pointing to auto-generated OpenAPI documentation with Deno diagnostics."""
    import subprocess
    import shutil
    
    deno_in_path = shutil.which("deno")
    deno_version = "Not available"
    
    if deno_in_path:
        try:
            deno_version = subprocess.check_output([deno_in_path, "--version"], stderr=subprocess.STDOUT).decode("utf-8")
        except Exception as e:
            deno_version = f"Error running deno: {e}"
            
    checked_paths = {}
    for p in ["/opt/render/.deno/bin/deno", os.path.expanduser("~/.deno/bin/deno")]:
        checked_paths[p] = os.path.exists(p)
        if os.path.exists(p):
            try:
                checked_paths[p + "_exec"] = subprocess.check_output([p, "--version"], stderr=subprocess.STDOUT).decode("utf-8")
            except Exception as e:
                checked_paths[p + "_exec_error"] = str(e)

    return {
        "message": "Antigravity FastAPI Downloader Server active",
        "docs_url": "/docs",
        "deno_in_path": deno_in_path,
        "deno_version": deno_version,
        "checked_paths": checked_paths,
        "PATH": os.environ.get("PATH", "")
    }

@app.get("/api/info")
def get_video_info(url: str):
    """Fetches details and thumbnail of a video without downloading."""
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")

    try:
        current_config = config.load_config()
        downloader = YtdlpDownloader(current_config)
        info = downloader.get_info(url)

        if not info:
            raise HTTPException(status_code=404, detail="Failed to retrieve video details")

        is_playlist = "entries" in info
        thumbnails = info.get("thumbnails", [])
        thumbnail_url = ""
        if thumbnails:
            thumbnail_url = thumbnails[-1].get("url", "")

        return {
            "title": info.get("title", "Unknown Title"),
            "uploader": info.get("uploader", "Unknown Channel"),
            "duration": info.get("duration", 0),
            "view_count": info.get("view_count", 0),
            "thumbnail": thumbnail_url,
            "is_playlist": is_playlist,
            "entries_count": len(info.get("entries", [])) if is_playlist else 0
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/thumbnail")
def get_thumbnail_proxy(url: str):
    """Proxies thumbnail requests to bypass client-side DNS or firewall restrictions."""
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")
    
    import urllib.request
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            content_type = response.headers.get('Content-Type', 'image/jpeg')
            image_data = response.read()
            return Response(content=image_data, media_type=content_type)
    except Exception as e:
        # Fallback to 1x1 transparent GIF
        transparent_pixel = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        return Response(content=transparent_pixel, media_type="image/gif")

@app.post("/api/download")
async def start_download(request: Request):
    """API endpoint to start a download task."""
    try:
        data = await request.json()
    except Exception:
        data = {}
        
    url = data.get("url")
    dl_type = data.get("type", "video")  # video or audio
    quality = data.get("quality")        # e.g., "1080p", "mp3"

    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    # Prevent concurrent downloads of the exact same URL
    with downloads_lock:
        for job in active_downloads.values():
            if job["url"] == url and job["status"] in ["pending", "downloading", "processing"]:
                raise HTTPException(status_code=400, detail="This video is already being downloaded!")

    download_id = str(uuid.uuid4())[:8]

    # Start download task in a background worker thread
    thread = threading.Thread(
        target=download_worker, 
        args=(download_id, url, dl_type, quality),
        daemon=True
    )
    thread.start()

    return {
        "success": True, 
        "download_id": download_id,
        "message": "Download task queued successfully"
    }

@app.get("/api/progress")
async def stream_progress():
    """SSE endpoint streaming active download states to the browser."""
    async def generate():
        while True:
            with downloads_lock:
                downloads_list = list(active_downloads.values())
            
            yield f"data: {json.dumps({'downloads': downloads_list})}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/api/history")
def get_history():
    """Returns a list of downloaded files in the download directory."""
    current_config = config.load_config()
    download_dir = current_config.get("download_dir", "downloads")
    
    # Resolve relative download directory relative to root workspace
    if not os.path.isabs(download_dir):
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(backend_dir)
        download_dir = os.path.join(root_dir, download_dir)
        
    files = []
    if os.path.exists(download_dir):
        for name in os.listdir(download_dir):
            file_path = os.path.join(download_dir, name)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                # Format file size
                size_bytes = stat.st_size
                if size_bytes > 1024 * 1024:
                    size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                elif size_bytes > 1024:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{size_bytes} B"

                # Check file extension to guess format
                _, ext = os.path.splitext(name)
                ftype = "audio" if ext.lower() in [".mp3", ".m4a", ".flac", ".ogg", ".wav"] else "video"

                files.append({
                    "name": name,
                    "size": size_str,
                    "time": time_strftime_compat(stat.st_mtime),
                    "type": ftype
                })
    
    # Sort files by newest modified time
    files.sort(key=lambda x: x["time"], reverse=True)
    return {"history": files}

@app.get("/api/downloads/{filename}")
def download_file(filename: str):
    """Serves a completed download file for browser download."""
    current_config = config.load_config()
    download_dir = current_config.get("download_dir", "downloads")
    
    if not os.path.isabs(download_dir):
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(backend_dir)
        download_dir = os.path.join(root_dir, download_dir)
        
    file_path = os.path.join(download_dir, filename)
    
    # Secure validation against directory traversal attacks
    if not os.path.abspath(file_path).startswith(os.path.abspath(download_dir)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        
    return FileResponse(file_path, media_type="application/octet-stream", filename=filename)

def time_strftime_compat(mtime):
    import time
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))

@app.get("/api/config")
def get_config():
    """Gets the configuration options."""
    return {"config": config.load_config()}

@app.post("/api/config")
async def save_config(request: Request):
    """Updates the configuration options."""
    try:
        new_config = await request.json()
    except Exception:
        new_config = {}
        
    current = config.load_config()
    for key in current:
        if key in new_config:
            current[key] = new_config[key]
    config.save_config(current)
    return {"success": True, "config": current}

if __name__ == "__main__":
    import uvicorn
    # Host on 127.0.0.1 (localhost) on port 5000
    print("Antigravity Web Downloader Server Starting...")
    print("Point your browser to http://127.0.0.1:5000/docs for Swagger APIs")
    uvicorn.run("main:app", host="127.0.0.1", port=5000, reload=True)
