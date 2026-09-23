"""S1: staged encode -> GGUF transformer (audit) -> 256² sanity images and 1024² step timing, fp16 vs bf16.

Usage: s1_gguf_load.py [official|uc] [fp16,bf16]
"""
import sys
import time

import numpy as np
import torch

from common import MODELS, SPIKES, MemWatch, save
import model_loader as ml
from mps_attention import install_mps_attention

PROMPT = 'A red fox sitting in fresh snow at sunrise, a wooden sign in front of it reads "Qwen 2.1".'
variant = sys.argv[1] if len(sys.argv) > 1 else 'official'
dtypes = (sys.argv[2] if len(sys.argv) > 2 else 'fp16,bf16').split(',')
result = {'variant': variant}

# Stage A: encode once, then release the text encoder.
with MemWatch() as watch:
    start = time.time()
    encoder = ml.text_encoder(MODELS, torch.float16)
    pipe = ml.pipeline(MODELS, text_encoder=encoder)
    with torch.no_grad():
        embeds, mask, _ = pipe.encode_prompt(PROMPT, device=ml.device())
    embeds = embeds.cpu()
    mask = None if mask is None else mask.cpu()
    del encoder, pipe
    ml.free()
    watch.sample(torch)
result['encode'] = {'seconds': round(time.time() - start, 1), 'tokens': int(embeds.shape[1]),
                    'mps_after_free_gb': round(torch.mps.driver_allocated_memory() / 1024**3, 2), **watch.summary()}
print('encode', result['encode'], flush=True)

for name in dtypes:
    dtype = ml.DTYPES[name]
    with MemWatch() as watch:
        start = time.time()
        transformer = ml.transformer(MODELS, variant, dtype)
        loaded = round(time.time() - start, 1)
        vae = ml.vae(MODELS)
        pipe = ml.pipeline(MODELS, transformer=transformer, vae=vae)
        install_mps_attention(pipe.transformer)
        watch.sample(torch)
        after_load = round(torch.mps.driver_allocated_memory() / 1024**3, 2)
        stamps = []

        def step(_pipe, i, t, kwargs):
            torch.mps.synchronize()
            stamps.append(time.time())
            return kwargs

        common = dict(prompt_embeds=embeds.to('mps', dtype), prompt_embeds_mask=None if mask is None else mask.to('mps'),
                      callback_on_step_end=step, generator=torch.Generator('cpu').manual_seed(42))
        with torch.no_grad():
            small = pipe(width=256, height=256, num_inference_steps=4, **common).images[0]
        small.save(SPIKES / f's1_{variant}_{name}_256.png')
        pixels = np.asarray(small.convert('RGBA')).astype(np.float32)
        sanity = {'std': round(float(pixels[..., :3].std()), 1), 'mean': round(float(pixels[..., :3].mean()), 1),
                  'alpha_mean': round(float(pixels[..., 3].mean()), 1)}
        stamps.clear()
        begin = time.time()
        with torch.no_grad():
            latents = pipe(width=1024, height=1024, num_inference_steps=3, output_type='latent', **common).images
        steps = [round(b - a, 2) for a, b in zip([begin] + stamps[:-1], stamps)]
        finite = bool(torch.isfinite(latents).all())
    result[name] = {'transformer_load_s': loaded, 'mps_after_load_gb': after_load, 'sanity_256': sanity,
                    'step_seconds_1024': steps, 'latents_finite_1024': finite, **watch.summary()}
    print(name, result[name], flush=True)
    del transformer, vae, pipe, latents
    ml.free()
save(f's1_gguf_{variant}', result)
