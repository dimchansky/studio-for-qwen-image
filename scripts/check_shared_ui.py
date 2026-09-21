"""Keep platform web interfaces identical without touching their native shells."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
mac = root / 'macos/web'
win = root / 'windows/web'
mac_files = {p.relative_to(mac) for p in mac.rglob('*') if p.is_file() and not p.name.startswith('.')}
win_files = {p.relative_to(win) for p in win.rglob('*') if p.is_file() and not p.name.startswith('.')}
assert mac_files == win_files, 'Web asset inventory differs'
for name in mac_files:
    assert (mac / name).read_bytes() == (win / name).read_bytes(), name
print('Shared UI matches on both platforms.')
