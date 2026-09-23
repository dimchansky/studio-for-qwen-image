"""Timings measured on this machine (DATA/perf.json), used for ETA estimates."""
import json
import threading
import time
from pathlib import Path

# Starting points for an M1 Max before any job has been measured (seconds).
DEFAULTS = {'step_per_mp': {'fp16': 14.0, 'bf16': 16.0}, 'load': 30.0, 'encode': 40.0, 'decode': 8.0, 'enhance': 90.0}
REFERENCE_WEIGHT = 0.25  # cached reference tokens cost a fraction of target tokens per step
LOCK = threading.Lock()
KEEP = 50


def _path(data):
    return Path(data) / 'perf.json'


def load(data):
    try:
        return json.loads(_path(data).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []


def record(data, sample):
    with LOCK:
        samples = (load(data) + [{**sample, 'time': time.time()}])[-KEEP:]
        temporary = _path(data).with_suffix('.tmp')
        temporary.write_text(json.dumps(samples), encoding='utf-8')
        temporary.replace(_path(data))


def work_units(width, height, references=0, reference_side=1024):
    return width * height / 1e6 + REFERENCE_WEIGHT * references * reference_side**2 / 1e6


def _average(values, default):
    values = [v for v in values if isinstance(v, (int, float)) and v > 0][-10:]
    return sum(values) / len(values) if values else default


def estimate(data, *, width, height, steps, count=1, references=0, reference_side=1024, cfg=1, enhance=False,
             dtype='fp16', cached_embeddings=False):
    samples = load(data)
    per_unit = _average([s['step_seconds'] / s['units'] for s in samples
                         if s.get('dtype') == dtype and s.get('units') and s.get('step_seconds')],
                        DEFAULTS['step_per_mp'].get(dtype, 15.0))
    step = per_unit * work_units(width, height, references, reference_side) * (2 if cfg > 1 else 1)
    parts = {
        'enhance': _average([s.get('enhance_seconds') for s in samples], DEFAULTS['enhance']) if enhance else 0,
        'encode': 0 if cached_embeddings else _average([s.get('encode_seconds') for s in samples], DEFAULTS['encode']),
        'load': _average([s.get('load_seconds') for s in samples], DEFAULTS['load']),
        'denoise': step * steps * count,
        'decode': DEFAULTS['decode'] * count * max(1.0, width * height / 1e6),
    }
    return {'seconds': round(sum(parts.values())), 'parts': {k: round(v) for k, v in parts.items()},
            'step_seconds': round(step, 1), 'measured': len(samples)}
