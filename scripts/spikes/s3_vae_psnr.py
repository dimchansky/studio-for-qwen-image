"""S3: VAE encode->decode round trip on CPU, MPS (stock) and MPS (patched AvgDown3D).

Pass: patched MPS >= 45 dB and within 0.5 dB of CPU. Stock MPS near 7 dB confirms the bug.
"""
import math
import sys
import time

import torch
from PIL import Image

from common import DATA, MODELS, MemWatch, save
import model_store
import mps_patches
from diffusers import AutoencoderKLQwenImage21
from diffusers.image_processor import VaeImageProcessor

path = sys.argv[1] if len(sys.argv) > 1 else DATA / 'testimages/space/2d02ee93-6278-4aa9-8fb9-3ca8d4c89dbb.webp'
image = Image.open(path).convert('RGBA')
width, height = image.width // 32 * 32, image.height // 32 * 32
processor = VaeImageProcessor(vae_scale_factor=16, vae_latent_channels=64)
pixels = processor.preprocess(image, height=height, width=width).unsqueeze(2)  # [1, 4, 1, H, W] in [-1, 1]
vae = AutoencoderKLQwenImage21.from_pretrained(model_store.base_dir(MODELS), subfolder='vae', torch_dtype=torch.float32)


def roundtrip(device):
    model = vae.to(device)
    start = time.time()
    with torch.no_grad():
        latent = model.encode(pixels.to(device)).latent_dist.mode()
        encoded = time.time()
        decoded = model.decode(latent, return_dict=False)[0][:, :, 0]
    if device == 'mps':
        torch.mps.synchronize()
    return decoded.float().cpu(), latent.float().cpu(), round(encoded - start, 2), round(time.time() - encoded, 2)


def psnr(a, b):
    a = ((a[:, :3] + 1) / 2).clamp(0, 1)
    b = ((b[:, :3] + 1) / 2).clamp(0, 1)
    mse = torch.mean((a - b) ** 2).item()
    return round(10 * math.log10(1 / mse), 2) if mse > 0 else float('inf')


result = {'image': str(path), 'size': [width, height]}
source = pixels[:, :, 0]
with MemWatch() as watch:
    cpu_out, cpu_latent, enc, dec = roundtrip('cpu')
    result['cpu'] = {'psnr': psnr(cpu_out, source), 'encode_s': enc, 'decode_s': dec}
    stock_out, stock_latent, enc, dec = roundtrip('mps')
    result['mps_stock'] = {'psnr': psnr(stock_out, source), 'encode_s': enc, 'decode_s': dec,
                           'latent_max_abs_diff_vs_cpu': round(float((stock_latent - cpu_latent).abs().max()), 4)}
    mps_patches.install()
    patched_out, patched_latent, enc, dec = roundtrip('mps')
    result['mps_patched'] = {'psnr': psnr(patched_out, source), 'encode_s': enc, 'decode_s': dec,
                             'psnr_vs_cpu_output': psnr(patched_out, cpu_out),
                             'latent_max_abs_diff_vs_cpu': round(float((patched_latent - cpu_latent).abs().max()), 4)}
result['memory'] = watch.summary()
result['pass'] = result['mps_patched']['psnr'] >= 45 and abs(result['mps_patched']['psnr'] - result['cpu']['psnr']) <= 0.5
save('s3_vae_psnr', result)
