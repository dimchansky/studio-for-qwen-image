"""Run the official prompt enhancer, then exit before Diffusers loads weights."""
import json
import os
from pathlib import Path
import sys
import traceback
from generation_options import exact_text, protect_text, validate_rewrite


def run(p, report):
    import torch
    import psutil
    from transformers import AutoModelForImageTextToText, AutoProcessor
    from prompt_enhancer import PROFILES, reference_image, messages_for, enhance
    profile=PROFILES['edit' if p.get('images') else 't2i']
    checkpoint=p['enhancer_path']
    images=[reference_image(Path(p['data'])/'images'/name,profile.image_max_pixels) for name in p.get('images',[])]
    request=protect_text(p['prompt'],exact_text(p['prompt'],p.get('exact_text','')))
    if p.get('transparent'):
        request+='\nThe output must be an RGBA image with a transparent background.'
    if p.get('ratio_mode')=='fixed':
        request+=f"\nCompose for a fixed {p['width']} by {p['height']} canvas."
    report(stage='正在加载提示词增强模型',progress=None)
    processor=AutoProcessor.from_pretrained(checkpoint,local_files_only=True,trust_remote_code=False)
    kwargs=dict(dtype=torch.bfloat16,low_cpu_mem_usage=True,local_files_only=True,trust_remote_code=False)
    if torch.cuda.is_available():
        # Leave room for the vision encoder, attention and generation cache.
        free,_=torch.cuda.mem_get_info()
        kwargs.update(device_map='auto',max_memory={0:max(512*1024**2,free-4*1024**3),'cpu':max(1024**3,int(psutil.virtual_memory().available*.7))},offload_folder=str(Path(p['data'])/'pe-offload'))
        model=AutoModelForImageTextToText.from_pretrained(checkpoint,**kwargs).eval()
    elif torch.backends.mps.is_available():
        model=AutoModelForImageTextToText.from_pretrained(checkpoint,**kwargs).to('mps').eval()
    else:
        raise RuntimeError('未检测到 GPU 加速，请检查 PyTorch 环境。')
    report(stage='正在增强提示词',progress=None)
    messages=messages_for(checkpoint,request,images)
    result=enhance(model,processor,messages,profile,p['seed'])
    validate_rewrite(result,len(images))
    # Keep explicit lettering unchanged, even when the scene description is English.
    result['positive_prompt']=protect_text(result['positive_prompt'],exact_text(p['prompt'],p.get('exact_text','')))
    report(stage='提示词增强完成',progress=0,rewrite=result)


if __name__=='__main__':
    p=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'));status=Path(p['status_path']);state={}
    def report(**values):
        state.update(values)
        from io_utils import atomic_json
        atomic_json(status,state)
    try:
        run(p,report)
    except Exception as error:
        traceback.print_exc()
        report(error=str(error),stage='提示词增强失败')
        sys.exit(1)
