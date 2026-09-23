"""One image job = up to three disposable processes, run serially with cancellation between them:
prompt enhancement (MLX), prompt encoding (text encoder) and diffusion (transformer + VAE).
Each process exits before the next loads, so their weights never share the 32 GB of memory.
"""
import contextlib
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import model_store
import perf
import staged_pipeline
from generation_options import RGBA_TEMPLATE, exact_text, plan_references, protect_text, resolve_size, validate_rewrite

EMBEDDINGS_KEPT = 24


class RetryInBf16(RuntimeError):
    pass


def run_child(worker, config, job, root, data, suffix):
    if job.get('cancel'):
        raise InterruptedError()
    stem = job['id'] + suffix
    inp = data / 'jobs' / (stem + '.input.json')
    out = data / 'jobs' / (stem + '.status.json')
    out.unlink(missing_ok=True)
    config = {**config, 'status_path': str(out)}
    inp.write_text(json.dumps(config), encoding='utf-8')
    process = None
    result = {}
    try:
        with (data / 'jobs' / (job['id'] + '.log')).open('a', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable, '-X', 'utf8', str(root / 'backend' / worker), str(inp)],
                                       stdout=log, stderr=log, env={**os.environ, 'PYTHONUTF8': '1',
                                       'PYTORCH_ENABLE_MPS_FALLBACK': '1', 'HF_HUB_OFFLINE': '1',
                                       'TRANSFORMERS_OFFLINE': '1', 'TOKENIZERS_PARALLELISM': 'false'})
            job['worker_pid'] = process.pid
            while True:
                if job.get('cancel'):
                    raise InterruptedError()
                if out.exists():
                    with contextlib.suppress(OSError, ValueError):
                        result = json.loads(out.read_text(encoding='utf-8'))
                        job.update({key: value for key, value in result.items() if key != 'rewrite'})
                if process.poll() is not None:
                    break
                time.sleep(.25)
            if out.exists():
                result = json.loads(out.read_text(encoding='utf-8'))
                job.update({key: value for key, value in result.items() if key != 'rewrite'})
            if job.get('cancel'):
                raise InterruptedError()
            if process.returncode == 3 and result.get('retry_dtype'):
                raise RetryInBf16()
            if process.returncode != 0:
                error = result.get('error')
                if not error:
                    with (data / 'jobs' / (job['id'] + '.log')).open('rb') as stream:
                        stream.seek(max(0, stream.seek(0, 2) - 16000))
                        tail = stream.read().decode(errors='replace').lower()
                    error = ('GPU 内存分配失败，图像生成已停止。请关闭其他占用内存的应用后重试，或选择较小的图片尺寸。'
                             if any(key in tail for key in ('failed to allocate mtlbuffer', 'oversized fused alloc',
                                                            'out of memory')) else '推理进程退出。请在模型设置查看日志。')
                raise RuntimeError(error)
        return result
    finally:
        job.pop('worker_pid', None)
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def prune_embeddings(cache):
    files = sorted(cache.glob('*.embeds.pt'), key=lambda path: path.stat().st_mtime)
    for path in files[:-EMBEDDINGS_KEPT]:
        path.unlink(missing_ok=True)


def run_image_job(job, payload, root, data, models):
    from PIL import Image
    images = payload.get('images', [])
    config = {**payload, 'models': str(models), 'data': str(data), 'job_id': job['id']}
    # A fresh seed for every job unless the user locked one: re-editing an image with the seed
    # and size that produced it makes the model return a near-copy.
    config['seed'] = payload['seed'] if payload['seed'] >= 0 else secrets.randbelow(2**32)
    timings = {}
    rewrite = None
    original = payload['prompt']
    if payload.get('enhance'):
        task = 'edit' if images else 't2i'
        config['enhancer_path'] = str(model_store.pe_dir(models, task))
        started = time.time()
        result = run_child('enhancer_worker.py', config, job, root, data, '.pe')
        timings['enhance_seconds'] = round(time.time() - started, 1)
        rewrite = result.get('rewrite', {})
        validate_rewrite(rewrite, len(images))
        config['prompt'] = rewrite['positive_prompt']
    else:
        config['prompt'] = protect_text(original, exact_text(original, payload.get('exact_text', '')))
    if payload.get('transparent'):
        config['prompt'] = RGBA_TEMPLATE.format(config['prompt'])
    sizes = []
    for name in images:
        with Image.open(data / 'images' / name) as image:
            sizes.append(image.size)
    config['width'], config['height'] = resolve_size(payload, rewrite, sizes)
    budget = float(os.environ.get('QWEN_STUDIO_KV_BUDGET_GB', '6'))
    config['reference_resolution'], config['kv_cache_gb'] = plan_references(
        len(images), config['width'], config['height'], budget)
    job.update(width=config['width'], height=config['height'], reference_resolution=config['reference_resolution'],
               progress=0, stage='正在理解提示词')

    cache = data / 'cache'
    cache.mkdir(exist_ok=True)
    arguments = staged_pipeline.call_arguments(config['prompt'], images, config.get('negative_prompt', ''),
                                               config.get('cfg', 1), config['width'], config['height'],
                                               config['reference_resolution'])
    digests = [staged_pipeline.file_digest(data / 'images' / name) for name in images]
    embeds = cache / (staged_pipeline.cache_key({**arguments, 'image': None}, digests) + '.embeds.pt')
    config['embeds_path'] = str(embeds)
    cached = embeds.is_file()
    if cached:
        os.utime(embeds)
    else:
        started = time.time()
        run_child('encode_worker.py', config, job, root, data, '.encode')
        timings['encode_seconds'] = round(time.time() - started, 1)
        prune_embeddings(cache)

    dtype = os.environ.get('QWEN_STUDIO_DTYPE', 'auto')
    dtype = 'fp16' if dtype == 'auto' else dtype
    job.update(progress=0, stage='正在加载图像模型')
    try:
        result = run_child('worker.py', {**config, 'dtype': dtype}, job, root, data, '.image')
    except RetryInBf16:
        dtype = 'bf16'
        job.update(progress=0, stage='正在切换精度')
        result = run_child('worker.py', {**config, 'dtype': dtype}, job, root, data, '.image')
    names = result.get('images') or ([result['image']] if result.get('image') else [])
    if not names:
        raise RuntimeError('没有收到生成图片。')
    for name in names:
        (data / 'images' / f"{job['id']}-preview.png").unlink(missing_ok=True)
    units = perf.work_units(config['width'], config['height'], len(images), config['reference_resolution'])
    perf.record(data, {'dtype': dtype, 'units': units, 'step_seconds': result.get('step_seconds'),
                       'load_seconds': result.get('load_seconds'), 'steps': config['steps'],
                       'cfg': config.get('cfg', 1), 'turbo': config.get('turbo', False), **timings})
    meta = {key: config.get(key) for key in ('width', 'height', 'steps', 'seed', 'count', 'transparent',
                                             'negative_prompt', 'cfg', 'ratio_mode', 'variant', 'turbo', 'preset',
                                             'reference_resolution')}
    meta.update(job_id=job['id'], mode='image', seconds=round(time.time() - job['started']), dtype=dtype,
                original_prompt=original, effective_prompt=config['prompt'],
                enhanced_prompt=rewrite['positive_prompt'] if rewrite else None,
                enhancer=('PE-I2I' if images else 'PE-T2I') if rewrite else None,
                seeds=result.get('seeds', [config['seed']]), reference_images=images,
                step_seconds=result.get('step_seconds'), cached_embeddings=cached)
    return dict(images=names, meta=meta)
