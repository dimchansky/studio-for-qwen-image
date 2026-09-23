"""S0: environment, MPS limits, the rank-5 F.pad bug and the pipeline signatures (no weights)."""
import inspect

import psutil
import torch
import torch.nn.functional as F

from common import save, versions

result = {'versions': versions(), 'mps_available': torch.backends.mps.is_available(),
          'ram_gb': round(psutil.virtual_memory().total / 1024**3, 1)}
result['recommended_max_memory_gb'] = round(torch.mps.recommended_max_memory() / 1024**3, 2)

# The bug: rank-5 F.pad along time on MPS returns wrong values for large frames.
torch.manual_seed(0)
x = torch.randn(1, 96, 1, 512, 512)
reference = F.pad(x, (0, 0, 0, 0, 1, 0))
on_mps = F.pad(x.to('mps'), (0, 0, 0, 0, 1, 0)).cpu()
concat = torch.cat([x.new_zeros(1, 96, 1, 512, 512), x], dim=2).to('mps').cpu()
result['pad_mps_max_abs_error'] = float((on_mps - reference).abs().max())
result['cat_mps_max_abs_error'] = float((concat - reference).abs().max())

# The patched AvgDown3D must equal the original exactly.
from diffusers.models.autoencoders.autoencoder_kl_qwenimage21 import QwenImage21AvgDown3D
import mps_patches

block = QwenImage21AvgDown3D(96, 192, factor_t=2, factor_s=2)
sample = torch.randn(1, 96, 1, 256, 256)
original = block(sample)
mps_patches.install()
patched_cpu = block(sample)
patched_mps = block(sample.to('mps')).cpu()
result['patch_equal_on_cpu'] = bool(torch.equal(original, patched_cpu))
result['patch_mps_max_abs_error'] = float((patched_mps - original).abs().max())

from diffusers import QwenImage21Pipeline
result['encode_prompt_params'] = list(inspect.signature(QwenImage21Pipeline.encode_prompt).parameters)
result['call_has_image_pad_mask'] = 'image_pad_mask' in inspect.signature(QwenImage21Pipeline.__call__).parameters
result['has_encode_vae_image'] = hasattr(QwenImage21Pipeline, '_encode_vae_image')
save('s0_env', result)
