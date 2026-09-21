"""Keep the local-file bootstrap catalog in sync with the canonical JSON files."""
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
for platform in ('macos', 'windows'):
    web = root / platform / 'web'
    messages = json.loads((web / 'locales.json').read_text(encoding='utf-8'))
    patterns = json.loads((web / 'locale-patterns.json').read_text(encoding='utf-8'))
    (web / 'locale-data.js').write_text('// Generated from locales.json and locale-patterns.json by scripts/build_locales.py.\nwindow.STUDIO_MESSAGES=' + json.dumps(messages, ensure_ascii=False) + ';\nwindow.STUDIO_PATTERNS=' + json.dumps(patterns, ensure_ascii=False) + ';\n', encoding='utf-8')
