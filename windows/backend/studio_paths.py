"""Per-user paths, with optional local settings and environment overrides."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def local_settings():
    path = ROOT / 'settings.local.json'
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}

def data_path():
    default = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'QwenStudio'
    return Path(os.environ.get('QWEN_STUDIO_DATA') or local_settings().get('data') or default).expanduser()

def model_path(data):
    # Explicit test/data overrides stay isolated from a developer's local settings.
    configured = None if os.environ.get('QWEN_STUDIO_DATA') else local_settings().get('model')
    return Path(os.environ.get('QWEN_STUDIO_MODEL') or configured or data / 'models/Qwen-Image-2.1').expanduser()
