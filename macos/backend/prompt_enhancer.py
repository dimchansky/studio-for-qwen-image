"""Qwen Studio's adapter for the published PE-T2I / PE-I2I inference contract.

Profiles and JSON fields: QwenLM/Qwen-Image-2.1 prompt_rewrite, revision
fb7ae1d1f9611cd91524d03c53c5246b36ac8577. System prompts stay with the separately
downloaded checkpoints. This module is original application code, not vendored
Qwen model/inference code.
"""
from dataclasses import dataclass
import json
from pathlib import Path

@dataclass(frozen=True)
class Profile:
    max_new_tokens: int
    presence_penalty: float
    temperature: float = 1.0
    top_p: float = 0.95
    top_k: int = 20
    min_p: float = 0.0
    image_max_pixels: int = 1024*1024

PROFILES={'t2i':Profile(16256,1.5),'edit':Profile(24000,0.0)}

def messages_for(checkpoint,prompt,images):
    system=(Path(checkpoint)/'system_prompt.txt').read_text(encoding='utf-8').strip()
    if not system:raise ValueError('提示词增强模型缺少系统提示词，请重新下载。')
    return [dict(role='system',content=[dict(type='text',text=system)]),
        dict(role='user',content=[dict(type='image',image=image) for image in images]+[dict(type='text',text=prompt)])]

def reference_image(path,max_pixels):
    from PIL import Image
    with Image.open(path) as source:
        # Like the image pipeline's text encoder, the enhancer sees transparency composited over white.
        if 'A' in source.getbands() or 'transparency' in source.info:
            rgba=source.convert('RGBA');image=Image.new('RGB',rgba.size,(255,255,255));image.paste(rgba,mask=rgba.getchannel('A'))
        else:image=source.convert('RGB')
    if image.width*image.height>max_pixels:
        scale=(max_pixels/(image.width*image.height))**.5
        image=image.resize((max(1,int(image.width*scale)),max(1,int(image.height*scale))),Image.Resampling.LANCZOS)
    return image

def parse_output(text):
    # The template pre-fills the opening thinking tag. Accept only the final answer.
    if '</think>' not in text:raise ValueError('提示词增强未返回完整结果，请重试。')
    answer=text.split('</think>',1)[1]
    decoder=json.JSONDecoder();result=None;position=0
    while position<len(answer):
        start=answer.find('{',position)
        if start<0:break
        try:
            candidate,length=decoder.raw_decode(answer[start:]);position=start+length
        except ValueError:
            position=start+1;continue
        if not isinstance(candidate,dict):continue
        prompt=candidate.get('rewritten_prompt') or candidate.get('rewrited_prompt')
        if isinstance(prompt,str) and prompt.strip():
            result=dict(positive_prompt=prompt.strip(),wh_ratio=candidate.get('wh_ratio') or '',ratio_follow=candidate.get('ratio_follow') or '',parse_ok=True)
    if result is None:raise ValueError('提示词增强未返回完整结果，请重试。')
    return result

def enhance_mlx(checkpoint,messages,profile,seed,report,thinking_budget=3072,images=()):
    """Run the PE checkpoint with mlx-vlm using the official sampling profile.

    Thinking is capped: after `thinking_budget` tokens mlx-vlm forces the closing tag so
    the answer is always produced on a slow machine (the official limit is 16k–24k tokens).
    """
    import time
    import mlx.core as mx
    from mlx_vlm import load, stream_generate
    model,processor=load(str(checkpoint))
    # mlx-vlm renders templates with enable_thinking=False by default; the PE requires thinking.
    prompt=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=True)
    if not prompt.rstrip().endswith('<think>'):raise ValueError('提示词增强模板未开启思考模式。')
    thinking_budget=min(thinking_budget,profile.max_new_tokens)
    max_tokens=min(profile.max_new_tokens,thinking_budget+4096)
    mx.random.seed(seed)
    text='';answer=False;last=0.0
    for response in stream_generate(model,processor,prompt,image=list(images) or None,max_tokens=max_tokens,
            temperature=profile.temperature,top_p=profile.top_p,top_k=profile.top_k,min_p=profile.min_p,
            presence_penalty=profile.presence_penalty or None,presence_context_size=max_tokens,
            enable_thinking=True,thinking_budget=thinking_budget):
        text+=response.text;answer=answer or '</think>' in text
        if time.time()-last>.5:
            last=time.time()
            report(pe_tokens=response.generation_tokens,pe_tps=round(response.generation_tps,1),pe_phase='answer' if answer else 'thinking')
    # The template pre-fills the opening tag, so only the closing tag appears in the output.
    return parse_output(text)
