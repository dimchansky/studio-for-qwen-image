"""Encode the prompt with the text encoder, save the embeddings and exit.

Runs as its own process so the ~10 GB text encoder is gone before the transformer loads.
"""
import json
import os
import sys
import time
import traceback
from pathlib import Path

from io_utils import atomic_json


def run(p, report):
    import torch
    from PIL import Image
    import model_loader
    import staged_pipeline

    models = Path(p['models'])
    images = [Image.open(Path(p['data']) / 'images' / name).copy() for name in p.get('images', [])]
    arguments = staged_pipeline.call_arguments(p['prompt'], images, p.get('negative_prompt', ''), p.get('cfg', 1),
                                               p['width'], p['height'], p['reference_resolution'])
    for dtype in ([torch.float16, torch.bfloat16] if p.get('encoder_dtype', 'fp16') == 'fp16' else [torch.bfloat16]):
        report(stage='正在加载文字编码器', progress=None)
        start = time.time()
        encoder = model_loader.text_encoder(models, dtype)
        pipe = model_loader.pipeline(models, text_encoder=encoder)
        report(stage='正在理解提示词', progress=None)
        packet = staged_pipeline.capture(pipe, **arguments)
        peak = torch.mps.driver_allocated_memory()
        del encoder, pipe
        model_loader.free()
        if staged_pipeline.finite(packet):
            break
        print(f'Non-finite embeddings with {dtype}; retrying in bfloat16.', flush=True)
    else:
        raise RuntimeError('文字编码结果无效，请重试。')
    target = Path(p['embeds_path'])
    temporary = target.with_suffix('.tmp')
    torch.save(packet, temporary)
    os.replace(temporary, target)
    report(stage='提示词编码完成', progress=None, encode_seconds=round(time.time() - start, 1),
           prompt_tokens=int(packet['positive'][0].shape[1]), encode_peak_gb=round(peak / 1024**3, 2))


if __name__ == '__main__':
    p = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    status = Path(p['status_path'])
    state = {}

    def report(**values):
        state.update(values)
        atomic_json(status, state)

    try:
        run(p, report)
    except Exception as error:
        traceback.print_exc()
        report(error=str(error), stage='提示词编码失败')
        sys.exit(1)
