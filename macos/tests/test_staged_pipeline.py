"""Capture/replay of prompt embeddings around a pipeline __call__ (no model weights)."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import torch
import staged_pipeline

class FakePipeline:
    """Calls encode_prompt like QwenImage21Pipeline.__call__: keywords only, negative second."""
    def __init__(self):self.encoded=[];self.used=None
    def encode_prompt(self,prompt,image=None,device=None,num_images_per_prompt=1,prompt_embeds=None,prompt_embeds_mask=None):
        self.encoded.append(prompt)
        value=float(len(prompt))
        return torch.full((1,3,4),value),None,torch.tensor([[False,bool(image),False]])
    def __call__(self,prompt,image=None,negative_prompt=None,true_cfg_scale=1.0,width=None,height=None,output_resolution=1024,num_inference_steps=40,**_):
        positive=self.encode_prompt(image=image,prompt=prompt,prompt_embeds=None,prompt_embeds_mask=None,device='cpu',num_images_per_prompt=1)
        negative=None
        if true_cfg_scale>1 and negative_prompt is not None:
            negative=self.encode_prompt(image=image,prompt=negative_prompt,prompt_embeds=None,prompt_embeds_mask=None,device='cpu',num_images_per_prompt=1)
        self.used=(positive,negative)
        return 'image'

class StagedPipeline(unittest.TestCase):
    def test_capture_stops_after_encoding(self):
        pipe=FakePipeline()
        packet=staged_pipeline.capture(pipe,**staged_pipeline.call_arguments('four',['ref'],'',1,1024,1024,1024))
        self.assertEqual(pipe.encoded,['four']);self.assertIsNone(pipe.used)
        self.assertIsNone(packet['negative']);self.assertEqual(float(packet['positive'][0][0,0,0]),4.0)
        self.assertTrue(bool(packet['positive'][2][0,1]))
        self.assertFalse(hasattr(pipe,'__dict__') and 'encode_prompt' in pipe.__dict__)
        self.assertTrue(staged_pipeline.finite(packet))
    def test_negative_prompt_is_captured_and_replayed_in_order(self):
        arguments=staged_pipeline.call_arguments('positive',[],'neg',2.5,1024,1024,1024)
        packet=staged_pipeline.capture(FakePipeline(),**arguments)
        self.assertEqual(float(packet['negative'][0][0,0,0]),3.0)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'packet.pt';torch.save(packet,path);packet=torch.load(path)
        pipe=FakePipeline();staged_pipeline.inject(pipe,packet,torch.float16)
        pipe(**arguments)
        self.assertEqual(pipe.encoded,[])
        positive,negative=pipe.used
        self.assertEqual(positive[0].dtype,torch.float16);self.assertEqual(float(positive[0][0,0,0]),8.0);self.assertEqual(float(negative[0][0,0,0]),3.0)
    def test_non_finite_embeddings_are_detected(self):
        packet={'positive':(torch.tensor([float('nan')]),None,None),'negative':None}
        self.assertFalse(staged_pipeline.finite(packet))
    def test_cache_key_covers_what_changes_embeddings(self):
        base=staged_pipeline.call_arguments('p',[],'',1,1024,1024,1024)
        key=staged_pipeline.cache_key(base,['a'])
        self.assertEqual(key,staged_pipeline.cache_key({**base,'width':2048,'height':512},['a']))
        for changed,digests in (({**base,'prompt':'q'},['a']),({**base,'output_resolution':768},['a']),(base,['b']),(staged_pipeline.call_arguments('p',[],'n',2,1024,1024,1024),['a'])):
            self.assertNotEqual(key,staged_pipeline.cache_key(changed,digests))

if __name__=='__main__':unittest.main()
