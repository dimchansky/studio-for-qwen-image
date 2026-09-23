"""Disposable diffusion process: GGUF transformer + VAE, embeddings from encode_worker.py.

Denoises every requested image to latents first, frees the transformer, then decodes:
a full-frame VAE decode needs ~9 GB extra at 1 MP even in fp16, which does not fit next
to the transformer in 32 GB of unified memory. Exit releases all GPU allocations.
"""
import json
import sys
import time
import traceback
from pathlib import Path

from io_utils import atomic_json

TURBO_WEIGHTS = 'Qwen-Image-2.1-viggle-turbo-4step-lora-r64.safetensors'
PREVIEW_FRACTIONS = (.4, .7, .9)
FULL_FRAME_PIXELS = 1_300_000  # larger outputs decode in overlapping tiles
EXIT_RETRY_BF16 = 3


class NonFinite(RuntimeError):
    pass


def decode(pipe, vae, latents, width, height, tile=None):
    import torch
    z = pipe._unpack_latents(latents.to(vae.device), height, width, pipe.vae_scale_factor).to(vae.dtype)
    mean = torch.tensor(vae.config.latents_mean).view(1, -1, 1, 1, 1).to(z)
    std = torch.tensor(vae.config.latents_std).view(1, -1, 1, 1, 1).to(z)
    if tile:
        vae.enable_tiling(tile, tile, tile - 128, tile - 128)
    else:
        vae.disable_tiling()
    with torch.no_grad():
        image = vae.decode(z * std + mean, return_dict=False)[0][:, :, 0]
    return pipe.image_processor.postprocess(image.float(), output_type='pil')[0]


def load_turbo(pipe, models, dtype):
    import model_store
    pipe.load_lora_weights(str(model_store.turbo_dir(models)), weight_name=TURBO_WEIGHTS, adapter_name='turbo')
    for name, parameter in pipe.transformer.named_parameters():
        if 'lora_' in name:
            parameter.data = parameter.data.to(dtype)


def run(p, report):
    import torch
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
    import model_loader
    import staged_pipeline
    from mps_attention import install_mps_attention

    models, data = Path(p['models']), Path(p['data'])
    dtype = model_loader.DTYPES[p.get('dtype', 'fp16')]
    width, height, steps, count = p['width'], p['height'], p['steps'], p.get('count', 1)
    report(stage='正在加载图像模型', progress=.02)
    started = time.time()
    transformer = model_loader.transformer(models, p.get('variant', 'official'), dtype)
    vae = model_loader.vae(models)
    pipe = model_loader.pipeline(models, transformer=transformer, vae=vae, turbo=p.get('turbo', False))
    if p.get('turbo'):
        load_turbo(pipe, models, dtype)
    install_mps_attention(pipe.transformer)
    # References are VAE-encoded in fp32 (the pipeline casts pixels to the embedding dtype first).
    encode_vae = pipe._encode_vae_image
    pipe._encode_vae_image = lambda image, generator: encode_vae(image.to(vae.dtype), generator).to(dtype)
    packet = torch.load(p['embeds_path'])
    references = [Image.open(data / 'images' / name).copy() for name in p.get('images', [])]
    arguments = staged_pipeline.call_arguments(p['prompt'], references, p.get('negative_prompt', ''), p.get('cfg', 1),
                                               width, height, p['reference_resolution'])
    report(load_seconds=round(time.time() - started, 1))

    previews_on = p.get('previews', True) and steps >= 10 and p.get('cfg', 1) <= 1
    preview_steps = {max(1, round(steps * fraction)) for fraction in PREVIEW_FRACTIONS}
    prediction = {}
    if previews_on:
        pipe.transformer.register_forward_hook(
            lambda _module, _args, output: prediction.update(velocity=output[0].detach()[:, -(width // 16) * (height // 16):]))
    timings, latents_list, seeds = [], [], []
    batch = 0

    def preview(latents, index):
        sigma = pipe.scheduler.sigmas[index].to(latents)
        # Flow matching: the clean image estimate is x_t - sigma_t * v.
        image = decode(pipe, vae, latents - sigma * prediction['velocity'], width, height, tile=384)
        image.thumbnail((384, 384), Image.Resampling.LANCZOS)
        name = f"{p['job_id']}-preview.png"
        target = data / 'images' / name
        temporary = target.with_suffix('.tmp')
        image.save(temporary, format='PNG')
        temporary.replace(target)
        report(preview=name, preview_step=batch * steps + index)

    peak = [0]

    def sample_memory():
        peak[0] = max(peak[0], torch.mps.driver_allocated_memory())

    def step(_pipe, i, _t, kwargs):
        latents = kwargs['latents']
        if not torch.isfinite(latents).all():
            raise NonFinite('non-finite latents')
        torch.mps.synchronize()
        sample_memory()
        timings.append(time.time())
        report(stage=f'正在生成 {i + 1} / {steps}', progress=.05 + .85 * (batch + (i + 1) / steps) / count)
        if previews_on and i + 1 in preview_steps and i + 1 < steps:
            try:
                preview(latents, i + 1)
            except Exception:
                traceback.print_exc()
        return kwargs

    denoise_started = time.time()
    for batch in range(count):
        seed = (p['seed'] + batch) % 2**32
        seeds.append(seed)
        staged_pipeline.inject(pipe, packet, dtype)
        timings.append(time.time())
        with torch.no_grad():
            latents = pipe(**arguments, num_inference_steps=steps, use_kv_cache=p.get('use_kv_cache', True),
                           generator=torch.Generator('cpu').manual_seed(seed), callback_on_step_end=step,
                           output_type='latent').images
        latents_list.append(latents.cpu())
    step_seconds = round((time.time() - denoise_started) / (steps * count), 2)
    report(stage='正在解码图片', progress=.92, step_seconds=step_seconds, denoise_peak_gb=round(peak[0] / 1024**3, 2))

    # Free the transformer before the full-frame decode.
    pipe.transformer = None
    del transformer
    model_loader.free()
    vae.to(torch.float16)
    tile = None if width * height <= FULL_FRAME_PIXELS else 768
    names = []
    settings = {key: p.get(key) for key in ('width', 'height', 'steps', 'cfg', 'negative_prompt', 'transparent',
                                             'variant', 'turbo', 'dtype', 'reference_resolution')}
    for index, latents in enumerate(latents_list):
        image = decode(pipe, vae, latents, width, height, tile)
        sample_memory()
        metadata = PngInfo()
        metadata.add_text('qwen_studio', json.dumps({**settings, 'prompt': p['prompt'], 'seed': seeds[index]},
                                                    ensure_ascii=False))
        name = p['job_id'] + (f'-{index + 1}' if count > 1 else '') + '.png'
        image.save(data / 'images' / name, pnginfo=metadata)
        names.append(name)
        report(stage='正在保存图片', progress=.92 + .08 * (index + 1) / count, completed_images=list(names))
    report(stage='完成', progress=1, image=names[0], images=names, seeds=seeds, step_seconds=step_seconds,
           seconds=round(time.time() - started, 1), peak_gb=round(peak[0] / 1024**3, 2))


if __name__ == '__main__':
    p = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    status = Path(p['status_path'])
    state = {}

    def report(**values):
        state.update(values)
        atomic_json(status, state)

    try:
        run(p, report)
    except NonFinite:
        traceback.print_exc()
        report(retry_dtype='bf16', stage='正在切换精度')
        sys.exit(EXIT_RETRY_BF16)
    except Exception as error:
        traceback.print_exc()
        message = str(error)
        if 'out of memory' in message.lower() or 'mtlbuffer' in message.lower():
            message = '内存不足。请关闭其他大型应用，或选择较小的尺寸、较少的参考图，再重试。\n' + message[:300]
        report(error=message, stage='生成失败')
        sys.exit(1)
