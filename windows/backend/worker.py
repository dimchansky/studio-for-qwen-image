"""Disposable CUDA inference process; releases all model memory on exit."""
import json, math, os, secrets, sys, time, traceback
from pathlib import Path
from generation_options import diffusion_kwargs
from io_utils import atomic_json, replace_with_retry
p=json.loads(Path(sys.argv[1]).read_text());status=Path(p['status_path'])
def report(**values):
    state.update(values);atomic_json(status,state)
state={}
try:
    report(stage='正在加载模型',progress=0.01)
    import torch
    from diffusers import QwenImage21Pipeline, AutoencoderKLQwenImage21
    from PIL import Image
    device='cuda' if torch.cuda.is_available() else 'cpu'
    if device=='cpu': raise RuntimeError('未检测到 GPU 加速，请检查 PyTorch 环境。')
    torch.set_num_threads(min(8,os.cpu_count() or 4))
    torch.backends.cuda.matmul.allow_tf32 = True
    # Load the original FP32 decoder directly; casting BF16 weights back to FP32 cannot recover precision.
    vae=AutoencoderKLQwenImage21.from_pretrained(p['model_path'],subfolder='vae',torch_dtype=torch.float32,local_files_only=True)
    pipe=QwenImage21Pipeline.from_pretrained(p['model_path'],vae=vae,torch_dtype=torch.bfloat16,local_files_only=True,low_cpu_mem_usage=True)
    # Offload whole components, keeping the 8B encoder and 7B denoiser from occupying GPU memory together.
    pipe.enable_model_cpu_offload(device=device)
    # The 256px tiled decoder introduces green/purple seams, even on a constant gray field.
    # Decode a complete image to preserve spatial context; never silently fall back to tiled output.
    pipe.vae.disable_tiling()
    if hasattr(pipe.vae,'disable_slicing'):pipe.vae.disable_slicing()
    assert not pipe.vae.use_tiling, 'Full-frame VAE decoding is required.'
    pipe.set_progress_bar_config(disable=True)
    report(decoder='full-frame-fp32',device=torch.cuda.get_device_name(0))
    seed=p.get('seed',-1);seed=secrets.randbelow(2**32) if seed<0 else seed
    prompt=p['prompt']
    if p.get('transparent'): prompt='This is an RGBA image with transparency. '+prompt+' The image has alpha channel and the background is transparent.'
    refs=[Image.open(Path(p['data'])/'images'/x).copy() for x in p.get('images',[])]
    latest_prediction={}
    batch_index=0;count=p.get('count',1)
    def remember_prediction(_module,_args,output):
        latest_prediction['noise']=output[0].detach()[:, -(p['width']//16)*(p['height']//16):]
    preview_hook=pipe.transformer.register_forward_hook(remember_prediction)
    preview_steps={max(1,round(p['steps']*fraction)) for fraction in (.4,.7,.9)}
    def preview(_pipe,latents,index):
        z=_pipe._unpack_latents(latents.detach(),p['height'],p['width'],_pipe.vae_scale_factor).float()
        # Preserve the latent grid: resizing latent channels creates colored artifacts.
        # Decode first, then resize the resulting image for the lightweight preview.
        mean=torch.tensor(_pipe.vae.config.latents_mean,device=z.device).view(1,-1,1,1,1)
        std=torch.tensor(_pipe.vae.config.latents_std,device=z.device).view(1,-1,1,1,1)
        decoded=_pipe.vae.decode((z*std+mean).to(_pipe.vae.dtype),return_dict=False)[0][:,:,0]
        im=_pipe.image_processor.postprocess(decoded,output_type='pil')[0]
        im.thumbnail((384,384),Image.Resampling.LANCZOS)
        name=p['job_id']+'-preview.png';target=Path(p['data'])/'images'/name;temp=target.with_suffix('.tmp')
        im.save(temp,format='PNG');replace_with_retry(temp,target)
        del decoded,z
        for hook in getattr(_pipe,'_all_hooks',[]):
            if hook.model is _pipe.vae:hook.offload();break
        report(preview=name,preview_step=batch_index*p['steps']+index)
    def step(_pipe,i,t,kwargs):
        report(stage=f'正在生成 {i+1} / {p["steps"]}',progress=.08+.87*(batch_index+(i+1)/p['steps'])/count)
        if i+1 in preview_steps and p['steps']>=10 and p.get('cfg',1)==1:
            try:
                z=kwargs['latents']
                sigma=_pipe.scheduler.sigmas[i+1].to(z)
                # Estimate the clean image from the flow velocity, rather than showing noisy latents.
                preview(_pipe,z-sigma*latest_prediction['noise'],i+1)
            except Exception: traceback.print_exc()
        return kwargs
    report(stage='正在理解画面',progress=.06,seed=seed)
    from PIL.PngImagePlugin import PngInfo
    images=[];seeds=[]
    # Reuse loaded weights, but render one image at a time to keep peak memory bounded.
    for batch_index in range(count):
        image_seed=(seed+batch_index)%(2**32);seeds.append(image_seed)
        kwargs=diffusion_kwargs(p,prompt)
        kwargs.update(generator=torch.Generator('cuda' if device=='cuda' else 'cpu').manual_seed(image_seed),callback_on_step_end=step)
        if refs:kwargs['image']=refs if len(refs)>1 else refs[0]
        result=pipe(**kwargs).images[0]
        report(stage='正在保存图片',progress=.08+.87*(batch_index+1)/count)
        metadata=PngInfo();metadata.add_text('qwen_studio',json.dumps({**{k:p.get(k) for k in ('width','height','steps','transparent','negative_prompt','cfg')},'prompt':prompt,'seed':image_seed,'decoder':'full-frame-fp32'},ensure_ascii=False))
        name=p['job_id']+(f'-{batch_index+1}' if count>1 else '')+'.png'
        result.save(Path(p['data'])/'images'/name,pnginfo=metadata);images.append(name)
        report(completed_images=list(images),batch_index=batch_index+1,batch_count=count)
    preview_hook.remove()
    report(stage='完成',progress=1,image=images[0],images=images,seed=seed,seeds=seeds,effective_prompt=prompt)
except Exception as e:
    traceback.print_exc()
    error=str(e)
    if 'out of memory' in error.lower(): error='内存不足。请关闭其他大型应用，将图片尺寸降至 512，再重试。\n'+error[:300]
    report(error=error,stage='生成失败');sys.exit(1)
