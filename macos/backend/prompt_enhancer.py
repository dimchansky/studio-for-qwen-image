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
    with Image.open(path) as source:image=source.convert('RGB')
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

def apply_presence(scores,token_ids,prompt_length,penalty):
    # Presence is an additive penalty on generated tokens only, not repetition.
    for row in range(token_ids.shape[0]):
        generated=token_ids[row,prompt_length:]
        if generated.numel():scores[row,generated.unique()]-=penalty
    return scores

def enhance(model,processor,messages,profile,seed):
    import torch
    from transformers import LogitsProcessor, LogitsProcessorList
    with torch.inference_mode():
        tokens=processor.apply_chat_template(messages,enable_thinking=True,add_generation_prompt=True,
            tokenize=True,return_dict=True,return_tensors='pt').to(model.device)
        if 'mm_token_type_ids' not in tokens and hasattr(processor,'create_mm_token_type_ids'):
            tokens['mm_token_type_ids']=processor.create_mm_token_type_ids(tokens['input_ids'])
        prefix=tokens['input_ids'].shape[1]
        class Presence(LogitsProcessor):
            def __call__(self,input_ids,scores):return apply_presence(scores,input_ids,prefix,profile.presence_penalty)
        processors=LogitsProcessorList([Presence()] if profile.presence_penalty else [])
        torch.manual_seed(seed)
        output=model.generate(**tokens,max_new_tokens=profile.max_new_tokens,do_sample=True,
            temperature=profile.temperature,top_p=profile.top_p,top_k=profile.top_k,min_p=profile.min_p,
            logits_processor=processors,pad_token_id=processor.tokenizer.eos_token_id)
        return parse_output(processor.tokenizer.decode(output[0,prefix:],skip_special_tokens=True))
