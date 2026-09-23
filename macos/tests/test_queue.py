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
 def test_missing_models_block_admission(self):
  with tempfile.TemporaryDirectory() as data:
   os.environ['QWEN_STUDIO_DATA']=data;os.environ['QWEN_STUDIO_TOKEN']='queue-test'
   spec=importlib.util.spec_from_file_location('queue_server_missing',Path(__file__).resolve().parents[1]/'backend/server.py')
   s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
   with s.connection() as c:c.execute('INSERT INTO sessions VALUES(?,?,?,?)',('s','新会话',0,0))
   with self.assertRaises(ValueError) as error:s.start_job(dict(session_id='s',prompt='x',width=1024,height=1024))
   self.assertIn('Transformer',str(error.exception))
   estimate=s.estimate(dict(width=1024,height=1024,preset='quality',images=[]))
   self.assertEqual(estimate['steps'],40);self.assertGreater(estimate['seconds'],0);self.assertTrue(estimate['missing'])
if __name__=='__main__':unittest.main()
