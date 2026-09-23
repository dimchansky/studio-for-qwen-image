"""Run the official prompt enhancer (MLX 4-bit), then exit before any image weights load."""
import json
import os
from pathlib import Path
import sys
import traceback
from generation_options import exact_text, protect_text, validate_rewrite


def run(p, report):
    from prompt_enhancer import PROFILES, reference_image, messages_for, enhance_mlx
    profile = PROFILES['edit' if p.get('images') else 't2i']
    checkpoint = p['enhancer_path']
    images = [reference_image(Path(p['data']) / 'images' / name, profile.image_max_pixels) for name in p.get('images', [])]
    request = protect_text(p['prompt'], exact_text(p['prompt'], p.get('exact_text', '')))
    if p.get('transparent'):
        request += '\nThe output must be an RGBA image with a transparent background.'
    if p.get('ratio_mode') == 'fixed':
        request += f"\nCompose for a fixed {p['width']} by {p['height']} canvas."
    report(stage='正在加载提示词增强模型', progress=None)
    messages = messages_for(checkpoint, request, images)
    budget = int(p.get('thinking_budget') or os.environ.get('QWEN_STUDIO_THINKING_BUDGET', '3072'))
    report(stage='正在增强提示词', progress=None)
    result = enhance_mlx(checkpoint, messages, profile, p['seed'], report, thinking_budget=budget, images=images)
    validate_rewrite(result, len(images))
    # Keep explicit lettering unchanged, even when the scene description is English.
    result['positive_prompt'] = protect_text(result['positive_prompt'], exact_text(p['prompt'], p.get('exact_text', '')))
    report(stage='提示词增强完成', progress=0, rewrite=result)


if __name__ == '__main__':
    p = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    status = Path(p['status_path'])
    state = {}

    def report(**values):
        state.update(values)
        from io_utils import atomic_json
        atomic_json(status, state)

    try:
        run(p, report)
    except Exception as error:
        traceback.print_exc()
        report(error=str(error), stage='提示词增强失败')
        sys.exit(1)
