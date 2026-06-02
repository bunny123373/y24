import json
import os

# Store config.json in root workspace folder (parent of backend/)
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
CONFIG_FILE = os.path.join(ROOT_DIR, "config.json")

DEFAULT_CONFIG = {
    "download_dir": "downloads",
    "video_quality": "best",  # best, 1080p, 720p, 480p
    "audio_format": "mp3",    # mp3, m4a, flac
    "audio_quality": "192",   # 128, 192, 256, 320 (kbps)
    "embed_metadata": True,
    "embed_thumbnail": True,
    "download_archive": True,  # Keep track of downloaded videos in a file to avoid duplicates
    "archive_file": "downloaded_history.txt",
    "restrict_filenames": False,
    "theme": "antigravity"
}

def load_config():
    """Loads config from root file or returns defaults if file doesn't exist."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                # Merge loaded config with defaults to ensure all keys exist
                return {**DEFAULT_CONFIG, **config_data}
        except Exception:
            # Fallback to default config on error
            return DEFAULT_CONFIG.copy()
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

def save_config(config_data):
    """Saves the config to root config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False
