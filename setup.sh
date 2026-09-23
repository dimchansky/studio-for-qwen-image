#!/bin/zsh
# Build the local runtime (.venv) for Studio for Qwen Image on an Apple Silicon Mac.
# Safe to re-run: it reuses .venv and only installs what is missing or pinned differently.
set -euo pipefail
cd "$(dirname "$0")"

fail() { print -u2 -- "✗ $*"; exit 1; }
warn() { print -- "! $*"; }

[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || fail 'This studio needs an Apple Silicon Mac (M1 or newer).'
macos="$(sw_vers -productVersion)"
(( ${macos%%.*} >= 14 )) || fail "macOS 14 or newer is required (found $macos)."

memory_gb=$(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 ))
(( memory_gb >= 32 )) || warn "This Mac has ${memory_gb} GB of memory. The studio is built for 32 GB or more; jobs will likely fail with out-of-memory errors."
free_gb=$(( $(df -k . | awk 'NR==2 {print $4}') / 1024 / 1024 ))
(( free_gb >= 30 )) || warn "Only ${free_gb} GB of disk space is free. Core model files need about 20 GB (39 GB with every optional file) plus 2 GB for the runtime."

# Python 3.12 (tested) or 3.13. An explicit interpreter wins; otherwise search the usual places.
find_python() {
  local candidate
  for candidate in "${QWEN_STUDIO_BOOTSTRAP_PYTHON:-}" python3.12 /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 \
      /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 python3.13 /opt/homebrew/bin/python3.13 \
      /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 python3; do
    [[ -n "$candidate" ]] || continue
    command -v "$candidate" >/dev/null 2>&1 || [[ -x "$candidate" ]] || continue
    if "$candidate" -c 'import sys, platform; assert sys.version_info[:2] in ((3, 12), (3, 13)) and platform.machine() == "arm64"' 2>/dev/null; then
      print -- "$candidate"; return 0
    fi
  done
  return 1
}

if [[ ! -x .venv/bin/python ]]; then
  python="$(find_python)" || fail 'Python 3.12 or 3.13 (arm64) was not found. Install it with "brew install python@3.12" or from python.org, then run ./setup.sh again.'
  print -- "Creating .venv with $("$python" -c 'import sys; print(sys.executable, sys.version.split()[0])')"
  "$python" -m venv .venv
fi
.venv/bin/python -c 'import sys; assert sys.version_info[:2] in ((3, 12), (3, 13))' 2>/dev/null \
  || fail '.venv uses an unsupported Python. Delete the .venv folder and run ./setup.sh again.'

export PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
.venv/bin/python -m pip install --quiet --upgrade pip
print -- 'Installing pinned packages (about 1.5 GB, a few minutes on the first run)…'
.venv/bin/python -m pip install --quiet -r macos/requirements.txt
.venv/bin/python - <<'PY'
import torch, diffusers, mlx.core as mx
from diffusers import QwenImage21Pipeline  # noqa: F401  (needs the pinned diffusers commit)
assert torch.backends.mps.is_available(), 'PyTorch cannot see the Apple GPU (MPS).'
print(f'✓ torch {torch.__version__} (MPS available), diffusers {diffusers.__version__}, mlx {mx.__version__}')
PY
print -- '✓ Setup complete. Next: ./download.sh (model files, ~20 GB), then ./run.sh'
