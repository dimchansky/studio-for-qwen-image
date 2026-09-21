"""Atomic worker updates that tolerate Windows readers briefly holding a file."""
import json
import time
from pathlib import Path


def replace_with_retry(source: Path, destination: Path, timeout: float = 3.0):
    deadline = time.monotonic() + timeout
    while True:
        try:
            source.replace(destination)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)


def atomic_json(destination: Path, value):
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    replace_with_retry(temporary, destination)
