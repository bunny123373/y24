import os
import sys
import uuid
import json
import time
import threading

# Reconfigure standard streams to UTF-8 on Windows to prevent UnicodeEncodeError
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from flask import Flask, render_template, request, jsonify, Response

import config
from downloader import YtdlpDownloader

app = Flask(__name__, template_folder="templates", static_folder="static")

# Thread-safe dictionary to keep track of active download jobs
active_downloads = {}
downloads_lock = threading.Lock()

def make_progress_hook(download_id):
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

def download_worker(download_id, url, dl_type, quality):
    """Background worker that handles fetching metadata and downloading media."""
    try:
        # Initialize download record
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
            # Quality override is format (mp3/m4a/flac) or bitrate if passed
            downloader_with_hook.download_audio(url, audio_format=quality)
        else:
            downloader_with_hook.download_video(url, resolution=quality)

        with downloads_lock:
            active_downloads[download_id].update({
                "status": "finished",
                "progress": 100,
                "eta": "Completed"
            })
    except Exception as e:
        with downloads_lock:
            active_downloads[download_id].update({
                "status": "failed",
                "error": str(e),
                "eta": "Failed"
            })

@app.route("/")
def index():
    """Serves the Web GUI main interface."""
    return render_template("index.html")

@app.route("/api/info")
def get_video_info():
    """Fetches details and thumbnail of a video without downloading."""
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "URL parameter is required"}), 400

    try:
        current_config = config.load_config()
        downloader = YtdlpDownloader(current_config)
        info = downloader.get_info(url)

        if not info:
            return jsonify({"error": "Failed to retrieve video details"}), 404

        is_playlist = "entries" in info
        thumbnails = info.get("thumbnails", [])
        thumbnail_url = ""
        if thumbnails:
            # Sort thumbnails by resolution if width/height exists, or get last
            thumbnail_url = thumbnails[-1].get("url", "")

        return jsonify({
            "title": info.get("title", "Unknown Title"),
            "uploader": info.get("uploader", "Unknown Channel"),
            "duration": info.get("duration", 0),
            "view_count": info.get("view_count", 0),
            "thumbnail": thumbnail_url,
            "is_playlist": is_playlist,
            "entries_count": len(info.get("entries", [])) if is_playlist else 0
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/download", methods=["POST"])
def start_download():
    """API endpoint to start a download task."""
    data = request.json or {}
    url = data.get("url")
    dl_type = data.get("type", "video")  # video or audio
    quality = data.get("quality")        # e.g., "1080p", "mp3"

    if not url:
        return jsonify({"error": "URL is required"}), 400

    # Prevent concurrent downloads of the exact same URL
    with downloads_lock:
        for job in active_downloads.values():
            if job["url"] == url and job["status"] in ["pending", "downloading", "processing"]:
                return jsonify({"error": "This video is already being downloaded!"}), 400

    download_id = str(uuid.uuid4())[:8]

    # Start download task in a background worker thread
    thread = threading.Thread(
        target=download_worker, 
        args=(download_id, url, dl_type, quality),
        daemon=True
    )
    thread.start()

    return jsonify({
        "success": True, 
        "download_id": download_id,
        "message": "Download task queued successfully"
    })

@app.route("/api/progress")
def stream_progress():
    """SSE endpoint streaming active download states to the browser."""
    def generate():
        while True:
            with downloads_lock:
                downloads_list = list(active_downloads.values())
            
            # Send data packet
            yield f"data: {json.dumps({'downloads': downloads_list})}\n\n"
            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream")

@app.route("/api/history")
def get_history():
    """Returns a list of downloaded files in the download directory."""
    current_config = config.load_config()
    download_dir = current_config.get("download_dir", "downloads")
    
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
                    "time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime)),
                    "type": ftype
                })
    
    # Sort files by newest modified time
    files.sort(key=lambda x: x["time"], reverse=True)
    return jsonify({"history": files})

@app.route("/api/config", methods=["GET", "POST"])
def manage_config():
    """Gets or updates the configuration options."""
    if request.method == "POST":
        new_config = request.json or {}
        current = config.load_config()
        # Update keys
        for key in current:
            if key in new_config:
                current[key] = new_config[key]
        config.save_config(current)
        return jsonify({"success": True, "config": current})
    else:
        return jsonify({"config": config.load_config()})

if __name__ == "__main__":
    # Host on 127.0.0.1 (localhost) on port 5000
    print("Antigravity Web Downloader Server Starting...")
    print("Point your browser to http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
