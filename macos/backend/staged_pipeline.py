"""Run QwenImage21Pipeline in two processes: prompt encoding, then denoising.

`__call__` cannot take precomputed embeddings together with condition images (it
never forwards `image_pad_mask`), so both stages run the real `__call__` and only
`encode_prompt` differs: the encode stage records its outputs and stops the call,
the denoise stage replays them. Image preprocessing stays upstream in both stages,
so shapes and masks match exactly.
"""
import hashlib
import json

import torch


class _Encoded(Exception):
    pass


def call_arguments(prompt, images, negative, cfg, width, height, reference_resolution):
    arguments = dict(prompt=prompt, image=images or None, width=width, height=height, true_cfg_scale=cfg,
                     output_resolution=reference_resolution)
    if cfg > 1 and negative:
        arguments['negative_prompt'] = negative
    return arguments


def capture(pipe, **arguments):
    """Encode the prompt (and negative prompt) exactly as `__call__` would; returns CPU tensors."""
    needed = 2 if 'negative_prompt' in arguments else 1
    outputs = []
    real = type(pipe).encode_prompt.__get__(pipe)

    def record(**kwargs):
        values = real(**kwargs)
        outputs.append(tuple(None if value is None else value.detach().cpu() for value in values))
        if len(outputs) == needed:
            raise _Encoded()
        return values

    pipe.encode_prompt = record
    try:
        with torch.no_grad():
            pipe(num_inference_steps=1, **arguments)
    except _Encoded:
        pass
    finally:
        del pipe.encode_prompt
    if len(outputs) != needed:
        raise RuntimeError('Prompt encoding did not complete.')
    return {'positive': outputs[0], 'negative': outputs[1] if needed == 2 else None}


def inject(pipe, packet, dtype):
    """Make the next `__call__` reuse captured embeddings instead of running the text encoder."""
    queue = [packet['positive']] + ([packet['negative']] if packet['negative'] is not None else [])

    def replay(device=None, **_kwargs):
        embeds, mask, image_mask = queue.pop(0)
        return (embeds.to(device, dtype), None if mask is None else mask.to(device),
                None if image_mask is None else image_mask.to(device))

    pipe.encode_prompt = replay


def finite(packet):
    return all(torch.isfinite(part[0]).all() for part in (packet['positive'], packet['negative']) if part is not None)


def cache_key(arguments, image_digests):
    """Embeddings depend on the prompt, negative prompt, references and the reference resolution only."""
    material = {key: arguments.get(key) for key in ('prompt', 'negative_prompt', 'output_resolution')}
    material['images'] = image_digests
    return hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:32]


def file_digest(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()
