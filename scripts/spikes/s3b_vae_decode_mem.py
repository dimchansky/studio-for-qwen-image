"""S3b: VAE decode cost on MPS only — full-frame fp32 vs fp16 vs larger tiles (1024x1024)."""
import math
import sys
import time

import torch
from PIL import Image

from common import DATA, MODELS, save
import model_store
import mps_patches
from diffusers import AutoencoderKLQwenImage21
from diffusers.image_processor import VaeImageProcessor

mps_patches.install()
size = int(sys.argv[1]) if len(sys.argv) > 1 else 1024
image = Image.open(DATA / 'testimages/space/0f5d38f9-d04a-498e-aaef-9dae01da8c6d.webp').convert('RGBA').resize((size, size))
pixels = VaeImageProcessor(vae_scale_factor=16, vae_latent_channels=64).preprocess(image, height=size, width=size).unsqueeze(2)
vae = AutoencoderKLQwenImage21.from_pretrained(model_store.base_dir(MODELS), subfolder='vae', torch_dtype=torch.float32).to('mps')
with torch.no_grad():
    latent = vae.encode(pixels.to('mps')).latent_dist.mode()
torch.mps.synchronize()


def gb(value):
    return round(value / 1024**3, 2)


def decode(label, dtype=torch.float32, tile=None):
    vae.to(dtype)
    if tile:
        vae.enable_tiling(tile, tile, tile - 64, tile - 64)
    else:
        vae.disable_tiling()
    torch.mps.empty_cache()
    base = torch.mps.driver_allocated_memory()
    start = time.time()
    with torch.no_grad():
        out = vae.decode(latent.to(dtype), return_dict=False)[0][:, :, 0].float()
    torch.mps.synchronize()
    seconds = round(time.time() - start, 2)
    peak = torch.mps.driver_allocated_memory()
    out = out.cpu()
    del_items = {'label': label, 'seconds': seconds, 'driver_peak_gb': gb(peak), 'extra_gb': gb(peak - base)}
    return out, del_items


rows = []
reference, row = decode('fp32 full-frame')
rows.append(row)
for label, dtype, tile in [('fp16 full-frame', torch.float16, None), ('fp32 tiles 512', torch.float32, 512),
                           ('fp32 tiles 768', torch.float32, 768)]:
    out, row = decode(label, dtype, tile)
    a = ((reference[:, :3] + 1) / 2).clamp(0, 1)
    b = ((out[:, :3] + 1) / 2).clamp(0, 1)
    mse = torch.mean((a - b) ** 2).item()
    row['psnr_vs_fp32_full'] = round(10 * math.log10(1 / mse), 2) if mse else float('inf')
    row['finite'] = bool(torch.isfinite(out).all())
    rows.append(row)
save(f's3b_vae_decode_mem_{size}', {'size': size, 'vae_weights_gb': gb(sum(p.numel() * 4 for p in vae.parameters())), 'rows': rows})
