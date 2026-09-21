"""Bound Qwen-Image 2.1 attention score allocations on Apple GPUs.

The stock MPS path can materialize a full float32 Q×K score matrix. At 2K,
32 heads need >32 GiB for that matrix alone. Slice query rows while retaining
ALL keys and values, preserving full-image attention and the official masks.
This is unrelated to VAE/image tiling: pixels are still decoded as one image.
"""
import torch

SCORE_BUDGET = 128 * 1024 * 1024

def bounded_attention(dispatch, query, key, value, *, score_budget=SCORE_BUDGET, **kwargs):
    # Diffusers dispatch tensors are [batch, sequence, heads, channels].
    bytes_per_row = query.shape[0] * query.shape[2] * key.shape[1] * 4
    chunk = max(1, score_budget // max(1, bytes_per_row))
    if query.shape[1] <= chunk:
        return dispatch(query, key, value, **kwargs)
    if kwargs.get('dropout_p', 0):
        raise ValueError('Memory-bounded attention is inference-only (dropout must be zero).')
    result = torch.empty((*query.shape[:-1], value.shape[-1]), dtype=query.dtype, device=query.device)
    mask = kwargs.get('attn_mask')
    for start in range(0, query.shape[1], chunk):
        end = min(start + chunk, query.shape[1])
        options = kwargs.copy()
        part_mask = mask
        if mask is not None and mask.shape[-2] != 1:
            part_mask = mask[..., start:end, :]
        if options.pop('is_causal', False):
            allowed = torch.arange(key.shape[1], device=query.device)[None, :] <= torch.arange(start, end, device=query.device)[:, None]
            if part_mask is None: part_mask = allowed
            elif part_mask.dtype == torch.bool: part_mask = part_mask & allowed
            else: part_mask = part_mask.masked_fill(~allowed, float('-inf'))
        options['attn_mask'] = None if part_mask is None else part_mask.contiguous()
        result[:, start:end] = dispatch(query[:, start:end].contiguous(), key, value, **options)
        # Complete each slice before submitting the next, so queued Metal work
        # cannot retain many temporary score matrices at the same time.
        if query.device.type == 'mps': torch.mps.synchronize()
    return result

def install_mps_attention(transformer):
    from diffusers.models.transformers import transformer_qwenimage21 as qwen
    # Keep Qwen's QKV projections, rotary positions, exact prefix segments and KV
    # cache handling. Only its attention dispatch is wrapped in this child process.
    if not getattr(qwen.dispatch_attention_fn, '_studio_bounded', False):
        original = qwen.dispatch_attention_fn
        def dispatch(query, key, value, **kwargs):
            if query.device.type != 'mps': return original(query, key, value, **kwargs)
            return bounded_attention(original, query, key, value, **kwargs)
        dispatch._studio_bounded = True
        qwen.dispatch_attention_fn = dispatch
    transformer.set_attn_processor(qwen.QwenImage21AttnProcessor())
