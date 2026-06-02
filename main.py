import os
import sys
import argparse

# Reconfigure standard streams to UTF-8 on Windows to prevent UnicodeEncodeError
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.progress import Progress, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
from rich.theme import Theme

import config
from downloader import YtdlpDownloader

THEMES = {
    "antigravity": Theme({
        "banner": "bold magenta",
        "accent": "cyan",
        "success": "bold green",
        "error": "bold red",
        "warning": "bold gold3",
        "highlight": "yellow"
    }),
    "cyberpunk": Theme({
        "banner": "bold #ff007f",
        "accent": "bold #00f0ff",
        "success": "bold #39ff14",
        "error": "bold #ff3131",
        "warning": "bold #ffff00",
        "highlight": "#ff007f"
    }),
    "dracula": Theme({
        "banner": "bold #bd93f9",
        "accent": "bold #ff79c6",
        "success": "bold #50fa7b",
        "error": "bold #ff5555",
        "warning": "bold #f1fa8c",
        "highlight": "#bd93f9"
    }),
    "nord": Theme({
        "banner": "bold #81a1c1",
        "accent": "bold #88c0d0",
        "success": "bold #a3be8c",
        "error": "bold #bf616a",
        "warning": "bold #ebcb8b",
        "highlight": "#88c0d0"
    }),
    "monokai": Theme({
        "banner": "bold #f92672",
        "accent": "bold #66d9ef",
        "success": "bold #a6e22e",
        "error": "bold #f92672",
        "warning": "bold #fd971f",
        "highlight": "#fd971f"
    })
}

# Load configuration first to set initial theme
_initial_config = config.load_config()
_initial_theme = THEMES.get(_initial_config.get("theme", "antigravity"), THEMES["antigravity"])
console = Console(theme=_initial_theme)

def update_console_theme(theme_name):
    """Updates the global console object with the selected theme."""
    global console
    selected_theme = THEMES.get(theme_name, THEMES["antigravity"])
    console = Console(theme=selected_theme)

class RichDownloadProgress:
    """Manages the rich progress bar during download hooks."""
    def __init__(self):
        self.progress = Progress(
            TextColumn("[accent]{task.description}"),
            BarColumn(style="dim", complete_style="accent"),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console
        )
        self.task_id = None
        self._last_file = ""

    def __enter__(self):
        self.progress.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.progress.stop()

    def hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            filename = os.path.basename(d.get('filename', 'Unknown File'))
            
            # Clip filename to fit progress display cleanly
            if len(filename) > 35:
                filename = filename[:32] + "..."

            if self.task_id is None or filename != self._last_file:
                # Start new task bar if it's the first file or file changed (e.g. video to audio stream)
                self._last_file = filename
                self.task_id = self.progress.add_task(
                    description=filename,
                    total=total if total > 0 else None
                )
            else:
                self.progress.update(
                    self.task_id,
                    completed=downloaded,
                    total=total if total > 0 else None,
                    description=filename
                )
        elif d['status'] == 'finished':
            if self.task_id is not None:
                self.progress.update(
                    self.task_id,
                    completed=d.get('total_bytes', d.get('downloaded_bytes', 0))
                )
                self.task_id = None
                self._last_file = ""

def format_duration(seconds):
    """Converts seconds into a readable HH:MM:SS duration string."""
    if not seconds:
        return "Unknown"
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def display_banner():
    """Prints a beautiful title banner."""
    console.print(Panel.fit(
        "[banner]▲ ANTIGRAVITY yt-dlp MEDIA DOWNLOADER ▲[/banner]\n"
        "[dim]An elegant, high-performance CLI media downloader[/dim]",
        border_style="banner",
        padding=(1, 4)
    ))

def display_video_info(info):
    """Displays video metadata in a neat table."""
    if not info:
        console.print("[error]Failed to retrieve video information.[/error]")
        return False

    title = info.get("title", "Unknown Title")
    uploader = info.get("uploader", "Unknown Channel")
    duration = format_duration(info.get("duration"))
    view_count = info.get("view_count", "N/A")
    if isinstance(view_count, int):
        view_count = f"{view_count:,}"

    table = Table(title="[success]Video Information[/success]", show_header=False, border_style="accent")
    table.add_column("Property", style="accent")
    table.add_column("Value")

    table.add_row("Title", title)
    table.add_row("Channel", uploader)
    table.add_row("Duration", duration)
    table.add_row("Views", str(view_count))
    
    if "webpage_url" in info:
        table.add_row("URL", info["webpage_url"])

    console.print(table)
    return True

def display_playlist_info(info):
    """Displays playlist metadata in a table."""
    if not info:
        console.print("[error]Failed to retrieve playlist information.[/error]")
        return False

    title = info.get("title", "Unknown Playlist")
    uploader = info.get("uploader", "Unknown Channel")
    entries = info.get("entries", [])
    count = len(entries)

    table = Table(title="[success]Playlist Information[/success]", show_header=False, border_style="accent")
    table.add_column("Property", style="accent")
    table.add_column("Value")

    table.add_row("Playlist Title", title)
    table.add_row("Channel/Creator", uploader)
    table.add_row("Total Items", f"{count} items")

    console.print(table)
    return True

def edit_settings(current_config):
    """Interactive loop to edit settings."""
    while True:
        table = Table(title="[banner]Current Configuration[/banner]", border_style="accent")
        table.add_column("Setting Key", style="accent")
        table.add_column("Current Value", style="success")
        table.add_column("Description", style="dim")

        table.add_row("1. download_dir", current_config["download_dir"], "Directory where files are saved")
        table.add_row("2. video_quality", current_config["video_quality"], "Max video resolution (best, 1080p, 720p, 480p)")
        table.add_row("3. audio_format", current_config["audio_format"], "Target audio extraction format (mp3, m4a, flac)")
        table.add_row("4. audio_quality", f"{current_config['audio_quality']} kbps", "Target audio bitrate (128, 192, 256, 320)")
        table.add_row("5. embed_metadata", str(current_config["embed_metadata"]), "Embed tags and details into the files")
        table.add_row("6. embed_thumbnail", str(current_config["embed_thumbnail"]), "Embed video cover thumbnail into files")
        table.add_row("7. download_archive", str(current_config["download_archive"]), "Keep a database to avoid downloading duplicates")
        table.add_row("8. theme", current_config["theme"], "Visual style of the downloader UI")
        
        console.print(table)
        console.print("[warning]Enter 1-8 to edit a setting, or 'b' to return to main menu.[/warning]")
        
        choice = Prompt.ask("Choose setting to edit", choices=["1", "2", "3", "4", "5", "6", "7", "8", "b", "B"])
        if choice.lower() == 'b':
            break

        if choice == "1":
            new_val = Prompt.ask("Enter new download directory", default=current_config["download_dir"])
            current_config["download_dir"] = new_val
        elif choice == "2":
            new_val = Prompt.ask("Enter default video quality", choices=["best", "1080p", "720p", "480p"], default=current_config["video_quality"])
            current_config["video_quality"] = new_val
        elif choice == "3":
            new_val = Prompt.ask("Enter default audio format", choices=["mp3", "m4a", "flac"], default=current_config["audio_format"])
            current_config["audio_format"] = new_val
        elif choice == "4":
            new_val = Prompt.ask("Enter default audio quality (kbps)", choices=["128", "192", "256", "320"], default=current_config["audio_quality"])
            current_config["audio_quality"] = new_val
        elif choice == "5":
            new_val = Confirm.ask("Embed metadata?", default=current_config["embed_metadata"])
            current_config["embed_metadata"] = new_val
        elif choice == "6":
            new_val = Confirm.ask("Embed thumbnail?", default=current_config["embed_thumbnail"])
            current_config["embed_thumbnail"] = new_val
        elif choice == "7":
            new_val = Confirm.ask("Use download history archive?", default=current_config["download_archive"])
            current_config["download_archive"] = new_val
        elif choice == "8":
            new_val = Prompt.ask("Enter theme", choices=list(THEMES.keys()), default=current_config["theme"])
            current_config["theme"] = new_val
            update_console_theme(new_val)

        config.save_config(current_config)
        console.print("[success]Configuration updated successfully![/success]\n")

def interactive_mode():
    """Main interactive menu system."""
    current_config = config.load_config()

    while True:
        display_banner()
        console.print("[accent]What would you like to do?[/accent]")
        console.print("1. [success]Download Video[/success]")
        console.print("2. [success]Download Audio (Extract MP3/M4A/FLAC)[/success]")
        console.print("3. [success]Download Playlist / Channel[/success]")
        console.print("4. [warning]Configuration Settings[/warning]")
        console.print("5. [red]Exit[/red]")

        choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "5"])

        if choice == "5":
            console.print("[bold yellow]Goodbye![/bold yellow]")
            sys.exit(0)

        # We initialize progress bar tracker
        progress_tracker = RichDownloadProgress()
        downloader = YtdlpDownloader(current_config, progress_hook=progress_tracker.hook)

        if choice == "1":
            url = Prompt.ask("[accent]Enter Video URL[/accent]")
            if not url.strip():
                continue

            with console.status("[warning]Fetching video metadata...[/warning]"):
                info = downloader.get_info(url)

            if not info:
                console.print("[error]Could not retrieve video details. Make sure the URL is valid.[/error]\n")
                continue

            # Check if url points to a playlist instead
            if "entries" in info:
                console.print("[warning]This URL points to a playlist. Please use option 3 to download playlists.[/warning]\n")
                continue

            display_video_info(info)

            confirm = Confirm.ask("Do you want to download this video?", default=True)
            if not confirm:
                continue

            # Check if user wants to override default resolution
            res_override = Prompt.ask(
                "Choose resolution (or press Enter for default)", 
                choices=["default", "best", "1080p", "720p", "480p"], 
                default="default"
            )
            res = None if res_override == "default" else res_override

            console.print(f"[success]Starting video download...[/success]")
            with progress_tracker:
                try:
                    downloader.download_video(url, resolution=res)
                    console.print("[success]✓ Download Completed successfully![/success]\n")
                except Exception as e:
                    console.print(f"[error]✗ An error occurred: {e}[/error]\n")

        elif choice == "2":
            url = Prompt.ask("[accent]Enter Video URL[/accent]")
            if not url.strip():
                continue

            with console.status("[warning]Fetching video metadata...[/warning]"):
                info = downloader.get_info(url)

            if not info:
                console.print("[error]Could not retrieve details. Make sure the URL is valid.[/error]\n")
                continue

            display_video_info(info)

            confirm = Confirm.ask("Do you want to extract audio from this video?", default=True)
            if not confirm:
                continue

            # Overrides
            fmt_override = Prompt.ask("Choose audio format (or press Enter for default)", choices=["default", "mp3", "m4a", "flac"], default="default")
            fmt = None if fmt_override == "default" else fmt_override

            qual_override = Prompt.ask("Choose audio quality (or press Enter for default)", choices=["default", "128", "192", "256", "320"], default="default")
            qual = None if qual_override == "default" else qual_override

            console.print(f"[success]Starting audio extraction...[/success]")
            with progress_tracker:
                try:
                    downloader.download_audio(url, audio_format=fmt, audio_quality=qual)
                    console.print("[success]✓ Audio Download & Extraction Completed successfully![/success]\n")
                except Exception as e:
                    console.print(f"[error]✗ An error occurred: {e}[/error]\n")

        elif choice == "3":
            url = Prompt.ask("[accent]Enter Playlist or Channel URL[/accent]")
            if not url.strip():
                continue

            with console.status("[warning]Fetching playlist details...[/warning]"):
                info = downloader.get_info(url)

            if not info:
                console.print("[error]Could not retrieve playlist details. Make sure the URL is valid.[/error]\n")
                continue

            # Verify it's actually a playlist
            if "entries" not in info:
                console.print("[warning]This URL points to a single video, not a playlist. Proceeding with single video download...[/warning]\n")
                display_video_info(info)
                confirm = Confirm.ask("Download video?", default=True)
                if confirm:
                    with progress_tracker:
                        downloader.download_video(url)
                    console.print("[success]✓ Download Completed successfully![/success]\n")
                continue

            display_playlist_info(info)

            confirm = Confirm.ask("Download this playlist?", default=True)
            if not confirm:
                continue

            download_type = Prompt.ask("Download playlist as Video or Audio?", choices=["video", "audio"], default="video")
            is_audio = (download_type == "audio")

            # Index range option
            range_opt = Confirm.ask("Download specific index range?", default=False)
            start_idx = None
            end_idx = None
            if range_opt:
                start_idx = IntPrompt.ask("Start index (1-based)", default=1)
                end_idx = IntPrompt.ask("End index (inclusive)", default=len(info.get("entries", [])))

            console.print(f"[success]Starting playlist download...[/success]")
            with progress_tracker:
                try:
                    downloader.download_playlist(url, is_audio=is_audio, start_idx=start_idx, end_idx=end_idx)
                    console.print("[success]✓ Playlist Download Completed successfully![/success]\n")
                except Exception as e:
                    console.print(f"[error]✗ An error occurred: {e}[/error]\n")

        elif choice == "4":
            edit_settings(current_config)

def run_cli_arguments():
    """Handles parsing CLI arguments and executing direct downloads."""
    parser = argparse.ArgumentParser(description="Antigravity Media Downloader CLI using yt-dlp")
    parser.add_argument("--url", "-u", type=str, help="URL of the video/playlist to download")
    parser.add_argument("--audio", "-a", action="store_true", help="Download/extract audio only")
    parser.add_argument("--resolution", "-r", type=str, choices=["best", "1080p", "720p", "480p"], help="Max resolution for video downloads")
    parser.add_argument("--format", "-f", type=str, choices=["mp3", "m4a", "flac"], help="Audio extraction format")
    parser.add_argument("--quality", "-q", type=str, choices=["128", "192", "256", "320"], help="Audio extraction quality (bitrate kbps)")
    parser.add_argument("--outtmpl", "-o", type=str, help="Output file naming template")
    parser.add_argument("--playlist", "-p", action="store_true", help="Treat URL as a playlist download")
    parser.add_argument("--range", type=str, help="Playlist index range to download (e.g. 1-5)")

    args = parser.parse_args()

    if not args.url:
        # Fallback to interactive mode if no url is provided
        interactive_mode()
        return

    current_config = config.load_config()
    progress_tracker = RichDownloadProgress()
    downloader = YtdlpDownloader(current_config, progress_hook=progress_tracker.hook)

    # Resolve overrides
    res = args.resolution or current_config.get("video_quality")
    audio_fmt = args.format or current_config.get("audio_format")
    audio_qual = args.quality or current_config.get("audio_quality")

    try:
        if args.playlist or "--playlist" in sys.argv:
            # Handle playlist range
            start_idx = None
            end_idx = None
            if args.range:
                try:
                    parts = args.range.split('-')
                    if len(parts) == 2:
                        start_idx = int(parts[0])
                        end_idx = int(parts[1])
                except ValueError:
                    console.print("[error]Invalid range format. Use e.g. 1-5[/error]")
                    sys.exit(1)

            console.print(f"[accent]Starting Playlist Download: {args.url}[/accent]")
            with progress_tracker:
                downloader.download_playlist(
                    args.url,
                    is_audio=args.audio,
                    start_idx=start_idx,
                    end_idx=end_idx,
                    outtmpl=args.outtmpl
                )
        else:
            # Single download
            if args.audio:
                console.print(f"[accent]Starting Audio Extraction: {args.url}[/accent]")
                with progress_tracker:
                    downloader.download_audio(
                        args.url,
                        audio_format=audio_fmt,
                        audio_quality=audio_qual,
                        outtmpl=args.outtmpl
                    )
            else:
                console.print(f"[accent]Starting Video Download: {args.url}[/accent]")
                with progress_tracker:
                    downloader.download_video(
                        args.url,
                        resolution=res,
                        outtmpl=args.outtmpl
                    )
        console.print("[success]✓ Completed successfully![/success]")
    except Exception as e:
        console.print(f"[error]✗ Error during execution: {e}[/error]")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_cli_arguments()
    else:
        interactive_mode()
