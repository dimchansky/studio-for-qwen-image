"""The MLX prompt enhancer uses the official profile, forces thinking and caps its length."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from prompt_enhancer import PROFILES, enhance_mlx

class Processor:
    def __init__(self,thinking=True):self.thinking=thinking;self.kwargs=None
    def apply_chat_template(self,messages,**kwargs):
        self.kwargs=kwargs
        return '<|im_start|>assistant\n<think>\n' if kwargs.get('enable_thinking') and self.thinking else '<|im_start|>assistant\n'

class Chunk:
    def __init__(self,text,n):self.text=text;self.generation_tokens=n;self.generation_tps=31.5

class EnhancerMLX(unittest.TestCase):
    def run_enhancer(self,profile,processor,budget=3072):
        calls={};reports=[]
        def stream(model,proc,prompt,**kwargs):
            calls.update(kwargs,prompt=prompt)
            yield Chunk('planning the scene ',10)
            yield Chunk('</think>{"rewritten_prompt":"A lighthouse at dawn, mist","wh_ratio":"16:9"}',42)
        with patch('mlx_vlm.load',return_value=('model',processor)),patch('mlx_vlm.stream_generate',stream),patch('time.time',side_effect=range(0,1000,1)):
            result=enhance_mlx('/checkpoint',[{'role':'user','content':[]}],profile,7,lambda **v:reports.append(v),thinking_budget=budget)
        return result,calls,reports
    def test_official_sampling_and_thinking(self):
        processor=Processor()
        result,calls,reports=self.run_enhancer(PROFILES['t2i'],processor)
        self.assertEqual(result['positive_prompt'],'A lighthouse at dawn, mist');self.assertEqual(result['wh_ratio'],'16:9')
        self.assertTrue(processor.kwargs['enable_thinking'])
        self.assertEqual((calls['temperature'],calls['top_p'],calls['top_k'],calls['presence_penalty']),(1.0,0.95,20,1.5))
        self.assertEqual(calls['thinking_budget'],3072);self.assertEqual(calls['max_tokens'],3072+4096)
        # mlx-vlm's presence window defaults to 20 tokens; the official penalty covers all generated tokens.
        self.assertEqual(calls['presence_context_size'],calls['max_tokens'])
        self.assertTrue(reports and reports[-1]['pe_tps']==31.5)
    def test_edit_profile_has_no_presence_penalty(self):
        _,calls,_=self.run_enhancer(PROFILES['edit'],Processor(),budget=100000)
        self.assertIsNone(calls['presence_penalty']);self.assertEqual(calls['thinking_budget'],24000)
    def test_template_without_thinking_is_rejected(self):
        with self.assertRaises(ValueError):self.run_enhancer(PROFILES['t2i'],Processor(thinking=False))

if __name__=='__main__':unittest.main()
