"""Keep platform web interfaces identical without touching their native shells."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
for name in ('app.js', 'index.html', 'style.css', 'CIRCLE_MENU_LICENSE.txt'):
    assert (root / 'macos/web' / name).read_bytes() == (root / 'windows/web' / name).read_bytes(), name
print('Shared UI matches on both platforms.')
