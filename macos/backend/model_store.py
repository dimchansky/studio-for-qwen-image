"""Pinned model components under DATA/models, described by models.json.

A component is ready when every file has its manifest size and the downloader
has written a verification marker after checking SHA-256 (hashing 10 GB files on
every status poll would be far too slow).
"""
import json
import os
import shutil
from pathlib import Path

MANIFEST = json.loads(Path(__file__).with_name('models.json').read_text(encoding='utf-8'))['components']
VARIANTS = {'official': 'transformer_official', 'uc': 'transformer_uc'}
PE_COMPONENTS = {'t2i': 'pe_t2i', 'edit': 'pe_i2i'}
STAGING = '.staging'


def reserve_bytes():
    return int(float(os.environ.get('QWEN_STUDIO_DISK_RESERVE_GB', '10')) * 1024**3)


def files(key):
    if key not in MANIFEST:
        raise ValueError(f'Unknown model component: {key}')
    return MANIFEST[key]['files']


def marker(models, key):
    return Path(models) / '.verified' / f'{key}.json'


def ready(models, key):
    models = Path(models)
    return marker(models, key).is_file() and all(
        (models / f['dest']).is_file() and (models / f['dest']).stat().st_size == f['size'] for f in files(key))


def partial_bytes(models):
    staging = Path(models) / STAGING
    if not staging.is_dir():
        return 0
    return sum(p.stat().st_size for p in staging.rglob('*.incomplete') if p.is_file())


def status(models, key):
    models = Path(models)
    done = sum(min((models / f['dest']).stat().st_size, f['size']) for f in files(key) if (models / f['dest']).is_file())
    return dict(ready=ready(models, key), bytes=done, total=MANIFEST[key]['total'],
                label=MANIFEST[key]['label'], required=MANIFEST[key]['required'])


def free_bytes(models):
    return shutil.disk_usage(Path(models)).free


# Locations inside DATA/models (they mirror the `dest` prefixes in models.json).
def base_dir(models):
    return Path(models) / 'Qwen-Image-2.1'


def text_encoder_dir(models):
    return Path(models) / 'text_encoder-sdnq8'


def transformer_file(models, variant):
    if variant not in VARIANTS:
        raise ValueError('Unknown transformer variant.')
    return Path(models) / files(VARIANTS[variant])[0]['dest']


def turbo_dir(models):
    return Path(models) / 'loras/viggle-turbo'


def pe_dir(models, task):
    return Path(models) / ('pe/t2i-mlx4' if task == 't2i' else 'pe/i2i-mlx4')


def required_components(variant='official', turbo=False, enhance_task=None):
    keys = ['base', 'text_encoder', VARIANTS[variant]]
    if turbo:
        keys.append('turbo')
    if enhance_task:
        keys.append(PE_COMPONENTS[enhance_task])
    return keys
