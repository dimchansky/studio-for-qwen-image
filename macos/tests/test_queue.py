"""Exercise the real serial scheduler with controlled workers; no GPU job required."""
import importlib.util,os,sys,tempfile,threading,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
class QueueTest(unittest.TestCase):
 def test_serial_send_cancel_and_history(self):
  with tempfile.TemporaryDirectory() as data:
   os.environ['QWEN_STUDIO_DATA']=data;os.environ['QWEN_STUDIO_TOKEN']='queue-test'
   spec=importlib.util.spec_from_file_location('queue_server',Path(__file__).resolve().parents[1]/'backend/server.py')
   s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
   with s.connection() as c:c.execute('INSERT INTO sessions VALUES(?,?,?,?)',('s','新会话',0,0))
   s.missing_components=lambda p:[]
   entered=[];gates={}
   def worker(job,payload):
    entered.append(job['id']);gates[job['id']]=threading.Event();gates[job['id']].wait(3)
    job['state']='done'
    with s.LOCK:s.ACTIVE=None;s.advance_queue()
   s.run_job=worker
   def submit(text):return s.start_job(dict(session_id='s',prompt=text,width=512,height=512,enhance=False,preset='turbo'))
   first=submit('first');second=submit('second');third=submit('third')
   self.assertEqual(first['state'],'running');self.assertEqual(second['state'],'queued')
   self.assertEqual(len(entered),1);self.assertEqual(len(s.read_session('s')['messages']),3)
   s.cancel_job(second['id']);self.assertEqual(second['state'],'cancelled')
   gates[first['id']].set()
   for _ in range(100):
    if third['id'] in gates:break
    time.sleep(.01)
   self.assertEqual(entered,[first['id'],third['id']]);self.assertEqual(third['state'],'running')
   gates[third['id']].set()
   for _ in range(100):
    if s.ACTIVE is None:break
    time.sleep(.01)
   self.assertIsNone(s.ACTIVE)
   # Completion timestamps follow queued user timestamps, but history must remain paired.
   with s.connection() as c:c.execute('DELETE FROM messages')
   for jid in ('a','b','c'):s.message('s','user',jid,meta={'job_id':jid})
   s.message('s','assistant','answer a',meta={'job_id':'a'})
   s.message('s','assistant','answer b',meta={'job_id':'b'})
   self.assertEqual([m['content'] for m in s.read_session('s')['messages']],['a','answer a','b','answer b','c'])
 def test_enhance_jobs_go_first_and_stay_out_of_the_chat(self):
  with tempfile.TemporaryDirectory() as data:
   os.environ['QWEN_STUDIO_DATA']=data;os.environ['QWEN_STUDIO_TOKEN']='queue-test'
   spec=importlib.util.spec_from_file_location('queue_server_enhance',Path(__file__).resolve().parents[1]/'backend/server.py')
   s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
   with s.connection() as c:c.execute('INSERT INTO sessions VALUES(?,?,?,?)',('s','新会话',0,0))
   s.missing_components=lambda p:[]
   order=[];gates={}
   def image(job,payload,*args):
    order.append(payload['prompt']);job['enhanced_prompt']='better '+payload['prompt']
    gates[job['id']]=threading.Event();gates[job['id']].wait(3)
    if job.get('cancel'):raise InterruptedError()
    return dict(images=['x.png'],meta={'job_id':job['id']})
   def enhance(job,payload,*args):
    order.append('enhance '+payload['prompt']);return dict(prompt='better '+payload['prompt'],width=1376,height=768)
   s.run_image_job=image;s.run_enhance_job=enhance
   def wait(check):
    for _ in range(300):
     if check():return
     time.sleep(.01)
    self.fail('timed out')
   first=s.start_job(dict(session_id='s',prompt='first',width=512,height=512,preset='turbo'))
   second=s.start_job(dict(session_id='s',prompt='second',width=512,height=512,preset='turbo'))
   quick=s.start_enhance(dict(prompt=' cabin ',width=1024,height=1024,ratio_mode='auto',images=[],negative_prompt='ignored'))
   # The enhancement waits only for the running image, not for the queued one.
   self.assertEqual([s.JOBS[jid]['mode'] for jid,_ in s.QUEUE],['enhance','image'])
   wait(lambda:first['id'] in gates);gates[first['id']].set()
   wait(lambda:quick['state']=='done');self.assertEqual(quick['result']['prompt'],'better cabin')
   wait(lambda:second['id'] in gates);self.assertEqual(order,['first','enhance cabin','second'])
   # A queued enhancement is cancelled without a chat message; a stopped image keeps its rewrite.
   late=s.start_enhance(dict(prompt='lake'));s.cancel_job(late['id']);self.assertEqual(late['state'],'cancelled')
   s.cancel_job(second['id']);gates[second['id']].set();wait(lambda:s.ACTIVE is None)
   messages=s.read_session('s')['messages']
   self.assertEqual([m['content'] for m in messages if m['role']=='user'],['first','second'])
   stopped=messages[-1]['meta'];self.assertTrue(stopped['cancelled'])
   self.assertEqual((stopped['original_prompt'],stopped['enhanced_prompt']),('second','better second'))
 def test_missing_models_block_admission(self):
  with tempfile.TemporaryDirectory() as data:
   os.environ['QWEN_STUDIO_DATA']=data;os.environ['QWEN_STUDIO_TOKEN']='queue-test'
   spec=importlib.util.spec_from_file_location('queue_server_missing',Path(__file__).resolve().parents[1]/'backend/server.py')
   s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
   with s.connection() as c:c.execute('INSERT INTO sessions VALUES(?,?,?,?)',('s','新会话',0,0))
   with self.assertRaises(ValueError) as error:s.start_job(dict(session_id='s',prompt='x',width=1024,height=1024))
   self.assertIn('Transformer',str(error.exception))
   with self.assertRaises(ValueError) as error:s.start_enhance(dict(prompt='x'))
   self.assertIn('PE-T2I',str(error.exception))
   estimate=s.estimate(dict(width=1024,height=1024,preset='quality',images=[]))
   self.assertEqual(estimate['steps'],40);self.assertGreater(estimate['seconds'],0);self.assertTrue(estimate['missing'])
if __name__=='__main__':unittest.main()
