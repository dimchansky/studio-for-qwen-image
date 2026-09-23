"""S2: SDNQ int8 text encoder on MPS — load time, memory, T2I and 1-reference encodes, CPU cross-check."""
import gc
import sys
import time

import torch
from PIL import Image

from common import DATA, MODELS, MemWatch, save
import model_store
import sdnq  # noqa: F401  (registers the SDNQ quantizer with transformers)
from diffusers import QwenImage21Pipeline, FlowMatchEulerDiscreteScheduler
from diffusers.pipelines.qwenimage21.pipeline_qwenimage21 import calculate_dimensions
from transformers import Qwen3VLForConditionalGeneration, Qwen3VLProcessor

T2I_PROMPT = 'A red fox sitting in fresh snow at sunrise, a wooden sign in front of it reads "Qwen 2.1".'
EDIT_PROMPT = 'Change the hairstyle to long voluminous wavy curls, keep everything else unchanged.'
REFERENCE = DATA / 'testimages/space/2d02ee93-6278-4aa9-8fb9-3ca8d4c89dbb.webp'
base = model_store.base_dir(MODELS)
processor = Qwen3VLProcessor.from_pretrained(base / 'processor')
scheduler = FlowMatchEulerDiscreteScheduler.from_pretrained(base, subfolder='scheduler')


def load(dtype, device):
    start = time.time()
    encoder = Qwen3VLForConditionalGeneration.from_pretrained(model_store.text_encoder_dir(MODELS), dtype=dtype)
    encoder = encoder.to(device).eval()
    pipe = QwenImage21Pipeline(scheduler=scheduler, vae=None, text_encoder=encoder, processor=processor, transformer=None)
    return pipe, round(time.time() - start, 1)


def reference_input(pipe, resolution=1024):
    image = Image.open(REFERENCE).convert('RGBA')
    width, height, _ = calculate_dimensions(resolution * resolution, image.width / image.height)
    return [pipe.image_processor.resize(image, width=width, height=height)]


def encode(pipe, device, prompt, images=None):
    start = time.time()
    with torch.no_grad():
        embeds, mask, image_mask = pipe.encode_prompt(prompt, image=images, device=torch.device(device))
    if device == 'mps':
        torch.mps.synchronize()
    return embeds.float().cpu(), {'seconds': round(time.time() - start, 2), 'tokens': embeds.shape[1],
                                  'finite': bool(torch.isfinite(embeds).all()),
                                  'abs_max': round(float(embeds.abs().max()), 2), 'std': round(float(embeds.std()), 3),
                                  'image_tokens': int(image_mask.sum()) if image_mask is not None else 0}


result = {}
dtypes = [torch.bfloat16, torch.float16] if '--fp16' in sys.argv else [torch.bfloat16]
for dtype in dtypes:
    name = str(dtype).split('.')[-1]
    with MemWatch() as watch:
        pipe, load_s = load(dtype, 'mps')
        t2i, t2i_info = encode(pipe, 'mps', T2I_PROMPT)
        t2i_again, again_info = encode(pipe, 'mps', T2I_PROMPT)
        _, edit_info = encode(pipe, 'mps', EDIT_PROMPT, reference_input(pipe))
    result[f'mps_{name}'] = {'load_s': load_s, 't2i': t2i_info, 't2i_warm': again_info, 'edit_1ref': edit_info,
                             'memory': watch.summary()}
    print(f'mps_{name}', result[f'mps_{name}'], flush=True)
    if dtype == torch.bfloat16:
        mps_bf16 = t2i
    del pipe
    gc.collect()
    torch.mps.empty_cache()

# CPU cross-check of the MPS numerics (text-only prompt, sequential to keep one copy in memory).
# float32 on CPU: bf16 GEMM on M1 CPUs falls back to a slow single-threaded kernel.
with MemWatch() as watch:
    pipe, load_s = load(torch.float32, 'cpu')
    cpu, cpu_info = encode(pipe, 'cpu', T2I_PROMPT)
cosine = torch.nn.functional.cosine_similarity(cpu.flatten(1), mps_bf16.flatten(1)).item()
result['cpu_fp32'] = {'load_s': load_s, 't2i': cpu_info, 'memory': watch.summary(),
                      'cosine_vs_mps_bf16': round(cosine, 5)}
result['pass'] = all(v['t2i']['finite'] for v in result.values() if isinstance(v, dict) and 't2i' in v) and cosine > 0.99
save('s2_text_encoder', result)
