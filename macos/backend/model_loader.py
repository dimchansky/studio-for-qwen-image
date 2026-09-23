"""Load Qwen-Image-2.1 components for staged, memory-bounded inference on Apple GPUs.

Weights come from DATA/models (see model_store.py). Each stage loads only what it
needs: the text encoder (SDNQ int8) for prompt encoding, then the GGUF transformer
and the VAE for denoising and decoding.
"""
import gc
from pathlib import Path

import torch

import model_store

DTYPES = {'fp16': torch.float16, 'bf16': torch.bfloat16, 'fp32': torch.float32}
# BF16 1-D tensors inside the GGUF files: without this list they stay packed as raw
# GGUF bytes and the zero-centred RMSNorm would read garbage.
KEEP_UNQUANTIZED = ['norm_q', 'norm_k', 'text_norm']


def device():
    if not torch.backends.mps.is_available():
        raise RuntimeError('未检测到 GPU 加速，请检查 PyTorch 环境。')
    return torch.device('mps')


def free(*_objects):
    """Drop references held by the caller first (del), then call this."""
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()


def processor(models):
    from transformers import Qwen3VLProcessor
    return Qwen3VLProcessor.from_pretrained(model_store.base_dir(models) / 'processor', local_files_only=True)


def scheduler(models, turbo=False):
    from diffusers import FlowMatchEulerDiscreteScheduler
    base = FlowMatchEulerDiscreteScheduler.from_pretrained(model_store.base_dir(models), subfolder='scheduler',
                                                           local_files_only=True)
    # The turbo distillation was trained without the terminal shift (its own scheduler config).
    return FlowMatchEulerDiscreteScheduler.from_config(base.config, shift_terminal=None) if turbo else base


def text_encoder(models, dtype=torch.float16):
    import sdnq  # noqa: F401  (registers the SDNQ quantizer with transformers)
    from transformers import Qwen3VLForConditionalGeneration
    # Load on CPU, then move: with device_map='mps' transformers casts the int8 SDNQ weights while
    # copying and loading stalls for minutes.
    model = Qwen3VLForConditionalGeneration.from_pretrained(model_store.text_encoder_dir(models), dtype=dtype,
                                                            local_files_only=True)
    return model.to(device()).eval()


def transformer(models, variant='official', dtype=torch.float16):
    from diffusers import GGUFQuantizationConfig, QwenImage21Transformer2DModel
    from diffusers.quantizers.gguf.utils import GGUFLinear, GGUFParameter
    config = GGUFQuantizationConfig(compute_dtype=dtype)
    config.modules_to_not_convert = KEEP_UNQUANTIZED
    model = QwenImage21Transformer2DModel.from_single_file(
        str(model_store.transformer_file(models, variant)), quantization_config=config, torch_dtype=dtype,
        config=str(model_store.base_dir(models)), subfolder='transformer', local_files_only=True)
    stray = [f'{module_name}.{name}' for module_name, module in model.named_modules() if not isinstance(module, GGUFLinear)
             for name, parameter in module.named_parameters(recurse=False) if isinstance(parameter, GGUFParameter)]
    if stray:
        raise RuntimeError(f'GGUF tensors left packed outside linear layers: {stray[:8]}')
    return model.to(device()).eval()


def vae(models, dtype=torch.float32):
    from diffusers import AutoencoderKLQwenImage21
    import mps_patches
    mps_patches.install()
    return AutoencoderKLQwenImage21.from_pretrained(model_store.base_dir(models), subfolder='vae', torch_dtype=dtype,
                                                    local_files_only=True).to(device()).eval()


def pipeline(models, *, text_encoder=None, transformer=None, vae=None, turbo=False):
    from diffusers import QwenImage21Pipeline
    pipe = QwenImage21Pipeline(scheduler=scheduler(models, turbo), vae=vae, text_encoder=text_encoder,
                               processor=processor(models), transformer=transformer)
    pipe.set_progress_bar_config(disable=True)
    return pipe


def gguf_path(models, variant):
    return Path(model_store.transformer_file(models, variant))
