import os
import yt_dlp
from typing import Dict, Any, Callable, Optional, List

class YtdlpDownloader:
    def __init__(self, config: Dict[str, Any], progress_hook: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.config = config
        self.progress_hook = progress_hook
        self.backend_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(self.backend_dir)

    def _get_base_opts(self, outtmpl: Optional[str] = None) -> Dict[str, Any]:
        """Generate base yt-dlp options from our configuration."""
        download_dir = self.config.get("download_dir", "downloads")
        
        # If relative path, resolve relative to root workspace
        if not os.path.isabs(download_dir):
            download_dir = os.path.join(self.root_dir, download_dir)
            
        os.makedirs(download_dir, exist_ok=True)

        if not outtmpl:
            outtmpl = os.path.join(download_dir, "%(title)s.%(ext)s")
        else:
            if not os.path.isabs(outtmpl):
                outtmpl = os.path.join(download_dir, outtmpl)

        opts = {
            "outtmpl": outtmpl,
            "restrictfilenames": self.config.get("restrict_filenames", False),
            "nocheckcertificate": True,
            "ignoreerrors": True,
            "logtostderr": False,
            "quiet": True,
            "no_warnings": True,
            "js_runtimes": {"node": {}},
            "extractor_args": {
                "youtube": {
                    "client": ["android", "ios"]
                }
            }
        }

        # Check for secure cookies.txt files
        cookies_paths = [
            os.path.join(self.root_dir, "cookies.txt"),
            "/etc/secrets/cookies.txt",
            os.path.join(self.backend_dir, "cookies.txt")
        ]
        cookiefile_path = None
        for path in cookies_paths:
            if os.path.exists(path):
                cookiefile_path = path
                break

        if cookiefile_path:
            # If the cookie file is read-only (like in Render secrets), yt-dlp will crash on exit when trying to save cookies.
            # To prevent this, we copy the cookies to a temporary writeable path and pass that instead.
            try:
                import tempfile
                import shutil
                temp_cookie_path = os.path.join(tempfile.gettempdir(), "temp_cookies.txt")
                shutil.copy2(cookiefile_path, temp_cookie_path)
                opts["cookiefile"] = temp_cookie_path
            except Exception:
                opts["cookiefile"] = cookiefile_path

        # Setup download archive if enabled
        if self.config.get("download_archive"):
            archive_file = self.config.get("archive_file", "downloaded_history.txt")
            if not os.path.isabs(archive_file):
                archive_file = os.path.join(self.root_dir, archive_file)
            opts["download_archive"] = archive_file

        if self.progress_hook:
            opts["progress_hooks"] = [self.progress_hook]

        return opts

    def get_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Extracts info dictionary for a URL without downloading."""
        ydl_opts = {
            "extract_flat": "in_playlist",  # Don't download/resolve playlist details fully, just get flat info
            "nocheckcertificate": True,
            "ignoreerrors": True,
            "quiet": True,
            "js_runtimes": {"node": {}},
            "extractor_args": {
                "youtube": {
                    "client": ["android", "ios"]
                }
            }
        }
        
        # Check for secure cookies.txt files
        cookies_paths = [
            os.path.join(self.root_dir, "cookies.txt"),
            "/etc/secrets/cookies.txt",
            os.path.join(self.backend_dir, "cookies.txt")
        ]
        cookiefile_path = None
        for path in cookies_paths:
            if os.path.exists(path):
                cookiefile_path = path
                break

        if cookiefile_path:
            # If the cookie file is read-only (like in Render secrets), yt-dlp will crash on exit when trying to save cookies.
            # To prevent this, we copy the cookies to a temporary writeable path and pass that instead.
            try:
                import tempfile
                import shutil
                temp_cookie_path = os.path.join(tempfile.gettempdir(), "temp_cookies.txt")
                shutil.copy2(cookiefile_path, temp_cookie_path)
                ydl_opts["cookiefile"] = temp_cookie_path
            except Exception:
                ydl_opts["cookiefile"] = cookiefile_path

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                return info
            except Exception as e:
                import sys
                print(f"ERROR: Failed extracting video details: {e}", file=sys.stderr)
                return None

    def download_video(self, url: str, resolution: Optional[str] = None, outtmpl: Optional[str] = None) -> Dict[str, Any]:
        """Downloads a video with the configured/specified resolution."""
        opts = self._get_base_opts(outtmpl)
        res = resolution or self.config.get("video_quality", "best")

        # Set format template based on resolution
        if res == "1080p":
            opts["format"] = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
        elif res == "720p":
            opts["format"] = "bestvideo[height<=720]+bestaudio/best[height<=720]"
        elif res == "480p":
            opts["format"] = "bestvideo[height<=480]+bestaudio/best[height<=480]"
        else:  # "best"
            opts["format"] = "bestvideo+bestaudio/best"

        # Enable merges for high quality split video/audio streams
        opts["merge_output_format"] = "mkv"  # MKV is highly compatible with all codecs

        postprocessors = []
        if self.config.get("embed_metadata"):
            postprocessors.append({
                "key": "FFmpegMetadata",
                "add_metadata": True,
            })

        if self.config.get("embed_thumbnail"):
            opts["writethumbnail"] = True
            postprocessors.append({
                "key": "EmbedThumbnail",
                "already_have_thumbnail": False,
            })

        if postprocessors:
            opts["postprocessors"] = postprocessors

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info

    def download_audio(self, url: str, audio_format: Optional[str] = None, audio_quality: Optional[str] = None, outtmpl: Optional[str] = None) -> Dict[str, Any]:
        """Downloads and extracts audio from a video."""
        opts = self._get_base_opts(outtmpl)
        fmt = audio_format or self.config.get("audio_format", "mp3")
        qual = audio_quality or self.config.get("audio_quality", "192")

        opts["format"] = "bestaudio/best"
        
        postprocessors = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": fmt,
                "preferredquality": qual,
            }
        ]

        if self.config.get("embed_metadata"):
            postprocessors.append({
                "key": "FFmpegMetadata",
                "add_metadata": True,
            })

        if self.config.get("embed_thumbnail"):
            opts["writethumbnail"] = True
            postprocessors.append({
                "key": "EmbedThumbnail",
                "already_have_thumbnail": False,
            })

        opts["postprocessors"] = postprocessors

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info

    def download_playlist(self, url: str, is_audio: bool = False, start_idx: Optional[int] = None, end_idx: Optional[int] = None, outtmpl: Optional[str] = None) -> Dict[str, Any]:
        """Downloads all or a range of items in a playlist."""
        opts = self._get_base_opts(outtmpl)
        
        # Override output template specifically for playlists if default is used
        if not outtmpl:
            download_dir = self.config.get("download_dir", "downloads")
            if not os.path.isabs(download_dir):
                download_dir = os.path.join(self.root_dir, download_dir)
            opts["outtmpl"] = os.path.join(download_dir, "%(playlist_title)s", "%(playlist_index)s - %(title)s.%(ext)s")

        if start_idx is not None:
            opts["playliststart"] = start_idx
        if end_idx is not None:
            opts["playlistend"] = end_idx

        # Configure quality
        if is_audio:
            fmt = self.config.get("audio_format", "mp3")
            qual = self.config.get("audio_quality", "192")
            opts["format"] = "bestaudio/best"
            postprocessors = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": fmt,
                    "preferredquality": qual,
                }
            ]
            if self.config.get("embed_metadata"):
                postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})
            if self.config.get("embed_thumbnail"):
                opts["writethumbnail"] = True
                postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
            opts["postprocessors"] = postprocessors
        else:
            res = self.config.get("video_quality", "best")
            if res == "1080p":
                opts["format"] = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
            elif res == "720p":
                opts["format"] = "bestvideo[height<=720]+bestaudio/best[height<=720]"
            elif res == "480p":
                opts["format"] = "bestvideo[height<=480]+bestaudio/best[height<=480]"
            else:
                opts["format"] = "bestvideo+bestaudio/best"
            
            opts["merge_output_format"] = "mkv"
            postprocessors = []
            if self.config.get("embed_metadata"):
                postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})
            if self.config.get("embed_thumbnail"):
                opts["writethumbnail"] = True
                postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
            if postprocessors:
                opts["postprocessors"] = postprocessors

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info
