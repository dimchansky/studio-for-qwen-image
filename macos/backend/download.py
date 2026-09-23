"""Download pinned model components one file at a time, verifying size and SHA-256.

Usage: download.py <models_dir> <component> [<component> ...]

Each file lands in DATA/models/.staging first and is moved into place only after
verification, so disk usage never exceeds the finished files plus one file in flight.
"""
import fcntl
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

from model_store import MANIFEST, STAGING, files, marker, ready, reserve_bytes


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(16 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def fetch(models, item):
    from huggingface_hub import hf_hub_download
    dest = models / item['dest']
    if dest.is_file() and dest.stat().st_size == item['size'] and sha256(dest) == item['sha256']:
        print('Verified', item['dest'], flush=True)
        return
    free = shutil.disk_usage(models).free
    if free < item['size'] + reserve_bytes():
        raise RuntimeError(f"Not enough disk space for {item['dest']}: {free / 1e9:.1f} GB free, "
                           f"{(item['size'] + reserve_bytes()) / 1e9:.1f} GB needed (file + reserve).")
    staging = models / STAGING / item['repo'].replace('/', '--')
    print('Downloading', item['repo'], item['path'], f"({item['size'] / 1e9:.2f} GB)", flush=True)
    for attempt in range(1, 4):
        try:
            got = Path(hf_hub_download(item['repo'], item['path'], revision=item['revision'], local_dir=staging))
            break
        except Exception as error:
            if attempt == 3:
                raise
            print(f'Retry {attempt}: {error}', flush=True)
            time.sleep(5 * attempt)
    if got.stat().st_size != item['size'] or sha256(got) != item['sha256']:
        got.unlink(missing_ok=True)
        raise RuntimeError(f"Checksum mismatch for {item['repo']}/{item['path']}; the file was discarded.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(got, dest)
    print('Completed', item['dest'], flush=True)


def main():
    models = Path(sys.argv[1])
    components = sys.argv[2:]
    unknown = [key for key in components if key not in MANIFEST]
    if not components or unknown:
        raise SystemExit(f'Usage: download.py <models_dir> <component>...; unknown: {unknown}')
    models.mkdir(parents=True, exist_ok=True)
    lock = (models / '.download.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('Download already running', flush=True)
        return
    (models / '.download.json').write_text(json.dumps({'pid': os.getpid(), 'components': components}), encoding='utf-8')
    try:
        for key in components:
            if ready(models, key):
                print('Ready', key, flush=True)
                continue
            for item in files(key):
                fetch(models, item)
            marker(models, key).parent.mkdir(parents=True, exist_ok=True)
            marker(models, key).write_text(json.dumps({'verified': time.time(), 'files': files(key)}), encoding='utf-8')
            print('Component ready', key, flush=True)
        shutil.rmtree(models / STAGING, ignore_errors=True)
    finally:
        (models / '.download.json').unlink(missing_ok=True)
        lock.close()


if __name__ == '__main__':
    main()
