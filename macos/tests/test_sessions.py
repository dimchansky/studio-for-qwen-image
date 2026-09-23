"""Deleting a chat removes its history and job files, and only the images no other chat uses."""
import importlib.util,os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
class DeleteSessionTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name)
  os.environ['QWEN_STUDIO_DATA']=self.tmp.name;os.environ['QWEN_STUDIO_TOKEN']='sessions-test'
  spec=importlib.util.spec_from_file_location('sessions_server',Path(__file__).resolve().parents[1]/'backend/server.py')
  self.s=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.s)
  with self.s.connection() as c:
   for sid in ('a','b'):c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(sid,'chat '+sid,0,0))
  # Chat a: an uploaded reference and two results. Chat b continues editing a's first result.
  self.s.message('a','user','edit',['ref.png'],{'job_id':'job1'})
  self.s.message('a','assistant','done',['out1.png'],{'job_id':'job1'})
  self.s.message('a','assistant','done',['out2.png'],{'job_id':'job2'})
  self.s.message('b','user','again',['out1.png'],{'job_id':'job3'})
  self.s.message('b','assistant','done',['out3.png'],{'job_id':'job3'})
  for name in ('ref.png','out1.png','out2.png','out3.png','job1-preview.png'):(self.data/'images'/name).write_bytes(b'png')
  for name in ('job1.log','job1.encode.input.json','job2.log','job3.log','job10.log'):(self.data/'jobs'/name).write_text('prompt')
 def tearDown(self):self.tmp.cleanup()
 def names(self,folder):return sorted(p.name for p in (self.data/folder).iterdir() if p.is_file())
 def test_delete_with_images_keeps_shared_files(self):
  self.s.JOBS['old']={'id':'old','session_id':'a','state':'done'}
  result=self.s.delete_session('a',True)
  self.assertEqual(result['deleted_images'],['out2.png','ref.png'])
  self.assertEqual(self.names('images'),['out1.png','out3.png'])
  self.assertEqual(self.names('jobs'),['job10.log','job3.log'])
  with self.assertRaises(ValueError):self.s.read_session('a')
  self.assertEqual(len(self.s.read_session('b')['messages']),2);self.assertNotIn('old',self.s.JOBS)
 def test_delete_without_images_keeps_every_image(self):
  self.assertEqual(self.s.delete_session('a')['deleted_images'],[])
  self.assertEqual(self.names('images'),['out1.png','out2.png','out3.png','ref.png'])
  self.assertEqual(self.names('jobs'),['job10.log','job3.log'])
 def test_running_job_blocks_deletion(self):
  self.s.JOBS['live']={'id':'live','session_id':'a','state':'running'}
  with self.assertRaises(ValueError):self.s.delete_session('a',True)
  self.assertEqual(len(self.s.read_session('a')['messages']),3);self.assertIn('ref.png',self.names('images'))
 def test_names_cannot_leave_the_data_folders(self):
  (self.data/'outside.png').write_bytes(b'png');(self.data/'x.log').write_text('keep')
  self.s.message('a','user','bad',['../outside.png'],{'job_id':'../x'})
  self.s.delete_session('a',True)
  self.assertTrue((self.data/'outside.png').is_file());self.assertTrue((self.data/'x.log').is_file())
if __name__=='__main__':unittest.main()
