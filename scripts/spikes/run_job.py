"""Run one real image job end to end (image_jobs -> encode_worker -> worker) and record memory.

Examples:
  run_job.py s4_t2i --prompt "..." --size 1024x1024 --preset standard
  run_job.py s7_edit1 --prompt "..." --image space/2d02ee93-....webp --preset custom --steps 12
"""
import argparse
import shutil
import threading
import time
import uuid

import psutil

from common import DATA, MODELS, ROOT, save, swap_used_gb
from generation_options import apply_preset, validate_options
import image_jobs

parser = argparse.ArgumentParser()
parser.add_argument('name')
parser.add_argument('--prompt', required=True)
parser.add_argument('--image', action='append', default=[], help='path under data/testimages (repeatable)')
parser.add_argument('--size', default='1024x1024')
parser.add_argument('--preset', default='standard')
parser.add_argument('--steps', type=int, default=25)
parser.add_argument('--variant', default='official')
parser.add_argument('--cfg', type=float, default=1)
parser.add_argument('--negative', default='')
parser.add_argument('--seed', type=int, default=42)
parser.add_argument('--count', type=int, default=1)
parser.add_argument('--transparent', action='store_true')
parser.add_argument('--enhance', action='store_true')
parser.add_argument('--ratio-mode', default='fixed')
parser.add_argument('--no-kv-cache', action='store_true')
args = parser.parse_args()

for folder in ('images', 'jobs'):
    (DATA / folder).mkdir(parents=True, exist_ok=True)
# References enter the studio the same way uploads do: as PNG files in DATA/images.
names = []
for relative in args.image:
    from PIL import Image
    source = DATA / 'testimages' / relative
    name = f'{args.name}-ref{len(names) + 1}.png'
    with Image.open(source) as image:
        image.convert('RGBA' if 'A' in image.getbands() else 'RGB').save(DATA / 'images' / name)
    names.append(name)

width, height = map(int, args.size.split('x'))
payload = dict(prompt=args.prompt, images=names, width=width, height=height, preset=args.preset, steps=args.steps,
               variant=args.variant, cfg=args.cfg, negative_prompt=args.negative, seed=args.seed, count=args.count,
               transparent=args.transparent, enhance=args.enhance, ratio_mode=args.ratio_mode,
               use_kv_cache=not args.no_kv_cache, previews=True, thinking_budget=3072)
validate_options(payload)
apply_preset(payload)
job = {'id': f'{args.name}-{uuid.uuid4().hex[:6]}', 'started': time.time(), 'session_id': 'spike'}

samples = {'min_available_gb': 99.0, 'swap_start_gb': swap_used_gb(), 'swap_peak_gb': 0.0, 'stages': []}
stop = threading.Event()


def watch():
    last_stage = None
    while not stop.is_set():
        available = psutil.virtual_memory().available / 1024**3
        samples['min_available_gb'] = round(min(samples['min_available_gb'], available), 2)
        samples['swap_peak_gb'] = round(max(samples['swap_peak_gb'], swap_used_gb()), 2)
        if job.get('stage') != last_stage:
            last_stage = job.get('stage')
            samples['stages'].append((round(time.time() - job['started'], 1), last_stage))
            print(f"[{samples['stages'][-1][0]:7.1f}s] {last_stage}", flush=True)
        stop.wait(1)


threading.Thread(target=watch, daemon=True).start()
error = None
try:
    result = image_jobs.run_image_job(job, payload, ROOT / 'macos', DATA, MODELS)
except Exception as exc:  # noqa: BLE001 - recorded in the summary
    error, result = repr(exc), None
stop.set()
outputs = []
if result:
    for image in result['images']:
        target = DATA / 'spikes' / f'{args.name}-{image}'
        shutil.copy(DATA / 'images' / image, target)
        outputs.append(str(target))
worker_state = {key: job.get(key) for key in ('step_seconds', 'load_seconds', 'encode_seconds', 'encode_peak_gb',
                                                'denoise_peak_gb', 'peak_gb', 'prompt_tokens', 'reference_resolution',
                                                'seconds', 'pe_tokens', 'pe_tps')}
save(args.name, {'payload': {k: v for k, v in payload.items() if k != 'prompt'}, 'prompt': args.prompt,
                 'seconds_total': round(time.time() - job['started'], 1), 'error': error, 'outputs': outputs,
                 'worker': worker_state, 'meta': result['meta'] if result else None, 'system': samples})
