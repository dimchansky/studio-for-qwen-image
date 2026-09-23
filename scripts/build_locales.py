"""Build macos/web/locale-data.js from the per-locale catalogs in macos/web/locales/.

Chinese is the source language: each other locale has <code>.json (exact strings) and
patterns-<code>.json (regular expressions for dynamic text).
"""
import json
from pathlib import Path

web = Path(__file__).resolve().parents[1] / 'macos' / 'web'
folder = web / 'locales'
codes = sorted(p.stem for p in folder.glob('*.json') if not p.stem.startswith('patterns-'))
messages = {code: json.loads((folder / f'{code}.json').read_text(encoding='utf-8')) for code in codes}
patterns = {code: json.loads((folder / f'patterns-{code}.json').read_text(encoding='utf-8')) for code in codes}
(web / 'locale-data.js').write_text(
    '// Generated from macos/web/locales by scripts/build_locales.py.\n'
    'window.STUDIO_MESSAGES=' + json.dumps(messages, ensure_ascii=False) + ';\n'
    'window.STUDIO_PATTERNS=' + json.dumps(patterns, ensure_ascii=False) + ';\n', encoding='utf-8')
print('Built locale-data.js for', ', '.join(codes))
