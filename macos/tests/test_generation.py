"""Contract checks without downloading weights or running model inference."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from generation_options import (validate_options, exact_text, protect_text, resolve_size, validate_rewrite, SIZES,
    apply_preset, plan_references, reference_tokens, RGBA_TEMPLATE)
from prompt_enhancer import PROFILES, parse_output, messages_for, reference_image
from image_jobs import run_child, run_enhance_job, run_image_job, RetryInBf16
import staged_pipeline

class GenerationContract(unittest.TestCase):
    def test_official_profiles_and_complete_answer(self):
        self.assertEqual((PROFILES['t2i'].presence_penalty,PROFILES['t2i'].max_new_tokens),(1.5,16256))
        self.assertEqual((PROFILES['edit'].presence_penalty,PROFILES['edit'].max_new_tokens),(0,24000))
        result=parse_output('planning </think>```json\n{"rewrited_prompt":"海报写着：第二次世界大战", "wh_ratio":"3:4"}\n```')
        validate_rewrite(result,0)
        self.assertIn('第二次世界大战',result['positive_prompt'])
        for value in ('unfinished planning', '</think>{"rewritten_prompt":', '</think>{"other":"value"}'):
            with self.assertRaises(ValueError):parse_output(value)
        for result in (dict(parse_ok=False),dict(parse_ok=True,positive_prompt='x',wh_ratio='1:1',ratio_follow='<image1>'),dict(parse_ok=True,positive_prompt='x',ratio_follow='<image3>')):
            with self.assertRaises(ValueError):validate_rewrite(result,2)
    def test_language_and_exact_text_survive(self):
        labels=exact_text('标题“第二次世界大战”，节点 "1939 年"','第二次世界大战\n1945 年')
        self.assertEqual(labels,['第二次世界大战','1945 年','1939 年'])
        prompt=protect_text('生成一张讲解二战历史的流程图',labels)
        self.assertIn('Simplified Chinese',prompt)
        for label in labels:self.assertIn(label,prompt)
    def test_ratios(self):
        p=dict(width=2048,height=2048,ratio_mode='auto',steps=40)
        for ratio,size in SIZES.items():self.assertEqual(resolve_size(p,{'wh_ratio':ratio}),size)
        self.assertEqual(resolve_size(p,{'ratio_follow':'<image2>'},[(100,100),(1600,900)]),(2720,1536))
        self.assertEqual(resolve_size({**p,'ratio_mode':'fixed'}, {'wh_ratio':'9:16'}),(2048,2048))
        # A 1K budget keeps the enhancer's ratio at about one megapixel.
        width,height=resolve_size({**p,'width':1024,'height':1024},{'wh_ratio':'16:9'})
        self.assertAlmostEqual(width/height,16/9,places=1);self.assertLess(abs(width*height-1024**2),0.05*1024**2)
    def test_cfg_requires_negative_prompt(self):
        for p in ({'cfg':2},{'negative_prompt':'blur'},{'cfg':float('nan')},{'count':5},{'enhance':'yes'},{'ratio_mode':'reference'}):
            with self.assertRaises(ValueError):validate_options(p)
        p={'negative_prompt':'blurry lettering','cfg':2,'count':4};validate_options(p)
        arguments=staged_pipeline.call_arguments('x',[],p['negative_prompt'],p['cfg'],1024,1024,1024)
        self.assertEqual(arguments['negative_prompt'],'blurry lettering')
        self.assertNotIn('negative_prompt',staged_pipeline.call_arguments('x',[],'ignored',1,1024,1024,1024))
    def test_presets(self):
        self.assertEqual(apply_preset({'preset':'turbo'})['steps'],4)
        self.assertTrue(apply_preset({'preset':'turbo'})['turbo'])
        self.assertEqual(apply_preset({'preset':'quality','steps':7})['steps'],40)
        self.assertEqual(apply_preset({'preset':'custom','steps':7})['steps'],7)
        for p in ({'preset':'turbo','cfg':2,'negative_prompt':'x'},{'preset':'fast'}):
            with self.assertRaises(ValueError):apply_preset(p)
        self.assertIn('RGBA',RGBA_TEMPLATE.format('a fox'))
    def test_reference_planner_keeps_cache_in_budget(self):
        for count in range(1,11):
            side,gib=plan_references(count,1024,1024,6)
            self.assertLessEqual(gib,6.0,count)
            self.assertIn(side,(1024,896,768,640,512,384))
        self.assertEqual(plan_references(1,1024,1024,6)[0],1024)
        self.assertEqual(plan_references(10,1024,1024,6)[0],384)
        # References never exceed 1024 px even for 2K output, and small canvases shrink them.
        self.assertEqual(plan_references(1,2048,2048,6)[0],1024)
        self.assertEqual(plan_references(1,512,512,6)[0],512)
        self.assertEqual(reference_tokens(1,1024,0),4096+1024)
    def test_reference_order_and_checkpoint_system_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'system_prompt.txt').write_text('checkpoint-specific')
            messages=messages_for(root,'change only image2',['first','second'])
            self.assertEqual(messages[0]['content'][0]['text'],'checkpoint-specific')
            self.assertEqual([v.get('image') for v in messages[1]['content'][:-1]],['first','second'])
            from PIL import Image
            path=root/'reference.png';Image.new('RGBA',(2400,1200)).save(path)
            image=reference_image(path,1024**2)
            self.assertLessEqual(image.width*image.height,1024**2)
            self.assertAlmostEqual(image.width/image.height,2,places=2)
            # Transparent pixels reach the enhancer composited over white, as in the image pipeline.
            self.assertEqual(image.mode,'RGB');self.assertEqual(image.getpixel((0,0)),(255,255,255))
    def job_files(self,root):
        for folder in ('images','jobs'):(root/folder).mkdir(exist_ok=True)
    def test_stages_run_in_order_and_meta_is_traceable(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.job_files(root);calls=[]
            def child(worker,config,job,*args):
                calls.append((worker,config.copy()))
                if worker=='enhancer_worker.py':return {'rewrite':dict(parse_ok=True,positive_prompt='A chart reading 第二次世界大战',wh_ratio='9:16')}
                if worker=='encode_worker.py':Path(config['embeds_path']).write_bytes(b'x');return {}
                return {'images':['a.png','b.png'],'seeds':[42,43],'step_seconds':9.5}
            p=dict(mode='image',prompt='生成一张讲解二战历史的流程图',width=2048,height=2048,steps=40,seed=42,enhance=True,ratio_mode='auto',images=[],count=2,transparent=True)
            job={'id':'test','started':time.time()}
            with patch('image_jobs.run_child',child):result=run_image_job(job,p,root,root,root)
            # The rewrite is on the job as soon as the enhancer is done, before the image exists.
            self.assertEqual(job['enhanced_prompt'],'A chart reading 第二次世界大战');self.assertEqual(result['meta']['enhanced_prompt'],job['enhanced_prompt'])
            self.assertEqual([c[0] for c in calls],['enhancer_worker.py','encode_worker.py','worker.py'])
            self.assertEqual((calls[2][1]['width'],calls[2][1]['height']),(1536,2752))
            self.assertTrue(calls[1][1]['prompt'].startswith('This is an RGBA image'))
            self.assertEqual(calls[2][1]['embeds_path'],calls[1][1]['embeds_path'])
            self.assertEqual(result['meta']['original_prompt'],p['prompt'])
            self.assertEqual(result['meta']['seeds'],[42,43])
            self.assertEqual(json.loads((root/'perf.json').read_text())[-1]['step_seconds'],9.5)
            # The same prompt again reuses the cached embeddings and skips the text encoder.
            calls.clear()
            with patch('image_jobs.run_child',child):result=run_image_job({'id':'again','started':time.time()},{**p,'enhance':False,'prompt':'A chart reading 第二次世界大战','ratio_mode':'fixed','width':1536,'height':2752},root,root,root)
            self.assertEqual([c[0] for c in calls],['worker.py']);self.assertTrue(result['meta']['cached_embeddings'])
            with patch('image_jobs.run_child',return_value={'rewrite':{}}) as run:
                with self.assertRaises(ValueError):run_image_job({'id':'test','started':time.time()},p,root,root,root)
                self.assertEqual(run.call_count,1)
    def test_enhance_only_returns_rewrite_and_canvas(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.job_files(root);calls=[]
            for name in ('e1.log','e1.pe.input.json','e10.log'):(root/'jobs'/name).write_text('prompt')
            def child(worker,config,job,*args):
                calls.append((worker,config.copy()))
                return {'rewrite':dict(parse_ok=True,raw_prompt='A cabin by a lake',positive_prompt='A cabin by a lake\nRender the following visible text exactly',wh_ratio='16:9')}
            p=dict(mode='enhance',prompt='домик у озера',width=1024,height=1024,ratio_mode='auto',images=[])
            with patch('image_jobs.run_child',child):result=run_enhance_job({'id':'e1'},p,root,root,root)
            # The composer gets the enhancer's own words and the 1K size of the ratio it chose.
            self.assertEqual(result,{'prompt':'A cabin by a lake','width':1376,'height':768})
            self.assertEqual([c[0] for c in calls],['enhancer_worker.py']);self.assertTrue(calls[0][1]['enhancer_path'].endswith('t2i-mlx4'))
            self.assertEqual([f.name for f in (root/'jobs').iterdir()],['e10.log'])
            with patch('image_jobs.run_child',child):self.assertEqual(run_enhance_job({'id':'e2'},{**p,'ratio_mode':'fixed'},root,root,root)['width'],1024)
            (root/'jobs'/'e3.log').write_text('prompt')
            with patch('image_jobs.run_child',side_effect=InterruptedError):
                with self.assertRaises(InterruptedError):run_enhance_job({'id':'e3'},p,root,root,root)
            self.assertFalse((root/'jobs'/'e3.log').exists())
    def test_embeddings_cache_and_random_edit_seed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.job_files(root);calls=[]
            from PIL import Image
            Image.new('RGB',(64,64),'red').save(root/'images'/'ref.png')
            def child(worker,config,job,*args):
                calls.append((worker,config.copy()))
                if worker=='encode_worker.py':Path(config['embeds_path']).write_bytes(b'x')
                return {'images':['out.png']} if worker=='worker.py' else {}
            p=dict(mode='image',prompt='make it blue',width=1024,height=1024,steps=4,seed=-1,enhance=False,ratio_mode='fixed',images=['ref.png'],count=1)
            with patch('image_jobs.run_child',child):
                first=run_image_job({'id':'one','started':time.time()},p,root,root,root)
                second=run_image_job({'id':'two','started':time.time()},p,root,root,root)
            self.assertEqual([c[0] for c in calls],['encode_worker.py','worker.py','worker.py'])
            self.assertTrue(second['meta']['cached_embeddings'])
            self.assertNotEqual(calls[1][1]['seed'],calls[2][1]['seed'])
    def test_fp16_overflow_retries_in_bf16(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.job_files(root);dtypes=[]
            def child(worker,config,job,*args):
                if worker=='encode_worker.py':Path(config['embeds_path']).write_bytes(b'x');return {}
                dtypes.append(config['dtype'])
                if config['dtype']=='fp16':raise RetryInBf16()
                return {'images':['out.png']}
            p=dict(mode='image',prompt='x',width=1024,height=1024,steps=4,seed=1,enhance=False,ratio_mode='fixed',images=[],count=1)
            with patch('image_jobs.run_child',child):result=run_image_job({'id':'t','started':time.time()},p,root,root,root)
            self.assertEqual(dtypes,['fp16','bf16']);self.assertEqual(result['meta']['dtype'],'bf16')
    def test_process_final_packet_and_cancel_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'backend').mkdir();(root/'jobs').mkdir()
            (root/'backend/fake.py').write_text('import json,sys;from pathlib import Path;p=json.loads(Path(sys.argv[1]).read_text());Path(p["status_path"]).write_text(json.dumps({"answer":"complete"}))')
            (root/'backend/retry.py').write_text('import json,sys;from pathlib import Path;p=json.loads(Path(sys.argv[1]).read_text());Path(p["status_path"]).write_text(json.dumps({"retry_dtype":"bf16"}));sys.exit(3)')
            job={'id':'sample'}
            self.assertEqual(run_child('fake.py',{},job,root,root,'.test')['answer'],'complete')
            with self.assertRaises(RetryInBf16):run_child('retry.py',{},{'id':'retry'},root,root,'.test')
            with self.assertRaises(InterruptedError):run_child('fake.py',{},dict(id='cancelled',cancel=True),root,root,'.test')
            self.assertFalse((root/'jobs/cancelled.test.input.json').exists())

if __name__=='__main__':unittest.main()
