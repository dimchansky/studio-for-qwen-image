"""Application controls mapped to the official Diffusers / PE contracts."""
import json
import math
import re


def validate_rewrite(result, image_count):
    if not result.get('parse_ok') or not result.get('positive_prompt','').strip():
        raise ValueError('提示词增强未返回完整结果，请重试。')
    ratio=result.get('wh_ratio','');reference=result.get('ratio_follow','')
    if not isinstance(ratio,str) or not isinstance(reference,str):raise ValueError('增强器返回了不支持的画布比例。')
    if bool(ratio)==bool(reference):raise ValueError('提示词增强未返回唯一的画布比例，请重试。')
    if ratio and ratio not in SIZES:raise ValueError('增强器返回了不支持的画布比例。')
    if reference:
        match=re.fullmatch(r'<image(\d+)>',reference)
        if not match or not 1<=int(match[1])<=image_count:raise ValueError('增强器返回了无效的参考图编号。')

SIZES={'1:1':(2048,2048),'4:3':(2400,1792),'3:4':(1792,2400),'3:2':(2528,1696),'2:3':(1696,2528),'16:9':(2752,1536),'9:16':(1536,2752)}

def exact_text(prompt, explicit=''):
    # Quote contents are literal artwork copy, never translated by the enhancer.
    quoted=re.findall(r'“([^”\n]+)”|「([^」\n]+)」|"([^"\n]+)"',prompt)
    values=[line.strip() for line in explicit.splitlines() if line.strip()]
    values += [next(v for v in match if v) for match in quoted]
    return list(dict.fromkeys(values))

def protect_text(prompt, labels):
    if re.search(r'[\u4e00-\u9fff]',prompt) and re.search(r'流程图|图表|海报|信息图|时间线',prompt) and not re.search(r'英文|英语|English',prompt,re.I):
        prompt+='\nKeep visible headings and labels in Simplified Chinese. Use concise, legible lettering with clear spacing.'
    if not labels:return prompt
    return prompt+'\nRender the following visible text exactly as written, preserving its original language and characters. Do not translate or replace this lettering: '+json.dumps(labels,ensure_ascii=False)

def validate_options(p):
    if not isinstance(p.get('enhance',True),bool):raise ValueError('提示词增强须为开关。')
    if p.get('ratio_mode','fixed') not in ('auto','fixed','reference'):raise ValueError('请选择有效的画布比例设置。')
    if p.get('ratio_mode')=='reference' and not p.get('images'):raise ValueError('跟随参考图比例需要先添加图片。')
    p['exact_text']=str(p.get('exact_text','')).strip()
    if len(p['exact_text'])>2000:raise ValueError('图中文字请限制在 2000 字以内。')
    p['negative_prompt']=str(p.get('negative_prompt','')).strip()
    if len(p['negative_prompt'])>16000:raise ValueError('反向提示词请限制在 16000 字以内。')
    p['cfg']=float(p.get('cfg',1))
    if not math.isfinite(p['cfg']) or not 1<=p['cfg']<=10:raise ValueError('引导强度须为 1–10。')
    if bool(p['negative_prompt'])!=(p['cfg']>1):raise ValueError('反向提示词需要同时设置大于 1 的引导强度。')
    p['count']=int(p.get('count',1))
    if not 1<=p['count']<=4:raise ValueError('每次生成数量须为 1–4。')
    if not isinstance(p.get('transparent',False),bool):raise ValueError('透明背景须为开关。')

def resolve_size(p,rewrite=None,image_sizes=()):
    mode=p.get('ratio_mode','fixed');width,height=p['width'],p['height']
    if mode=='fixed':return width,height
    rewrite=rewrite or {};reference=rewrite.get('ratio_follow','');ratio=rewrite.get('wh_ratio','')
    if mode=='reference':reference='<image1>';ratio=''
    if reference:
        match=re.fullmatch(r'<image(\d+)>',reference)
        if not match or not 1<=int(match[1])<=len(image_sizes):raise ValueError('增强器返回了无效的参考图编号。')
        iw,ih=image_sizes[int(match[1])-1]
        # Preserve the reference ratio at the selected area without stretching it.
        factor=min(math.sqrt(width*height/(iw*ih)),2752/max(iw,ih))
        w=max(256,round(iw*factor/32)*32);h=max(256,round(ih*factor/32)*32)
        if w*h>4_300_800:
            factor=math.sqrt(4_300_800/(w*h));w=int(w*factor//32)*32;h=int(h*factor//32)*32
        return w,h
    if ratio:
        if ratio not in SIZES:raise ValueError('增强器返回了不支持的画布比例。')
        rw,rh=SIZES[ratio]
        # Official sizes at 2K, and the same ratio for an explicit smaller budget.
        if width*height>=2048**2:return rw,rh
        factor=math.sqrt(width*height/(rw*rh))
        return max(256,round(rw*factor/32)*32),max(256,round(rh*factor/32)*32)
    return width,height


def diffusion_kwargs(p,prompt):
    """Keep the reference-image pixel budget tied to area, including wide canvases."""
    options=dict(prompt=prompt,width=p['width'],height=p['height'],num_inference_steps=p['steps'],
        output_resolution=round(math.sqrt(p['width']*p['height'])),use_kv_cache=True,
        true_cfg_scale=p.get('cfg',1),num_images_per_prompt=1)
    if p.get('negative_prompt'):options['negative_prompt']=p['negative_prompt']
    return options
