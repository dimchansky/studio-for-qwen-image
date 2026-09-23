"""Preferences survive two actual backend launches with different loopback origins."""
import json,os,subprocess,sys,tempfile,urllib.request,urllib.error
from pathlib import Path
server=Path(__file__).resolve().parents[1]/'backend/server.py'
with tempfile.TemporaryDirectory() as data:
 env={**os.environ,'QWEN_STUDIO_DATA':data,'PYTHONUNBUFFERED':'1'}
 env.pop('QWEN_STUDIO_TOKEN',None)
 def launch():
  p=subprocess.Popen([sys.executable,str(server)],env=env,stdout=subprocess.PIPE,text=True)
  port=json.loads(p.stdout.readline())['port']
  return p,port
 def token():return Path(data,'.token').read_text().strip()
 def request(port,body=None,path='preferences'):
  req=urllib.request.Request(f'http://127.0.0.1:{port}/api/{path}',data=None if body is None else json.dumps(body).encode(),headers={'X-Studio-Token':token(),'Content-Type':'application/json'})
  with urllib.request.urlopen(req) as response:return json.load(response)
 expected={'welcome_language':'ru','welcome_cycle':False,'interface_language':'ru','transformer_variant':'uc','preset':'turbo','thinking_budget':1024}
 p,first=launch()
 try:
  assert request(first)['transformer_variant']=='official'
  assert request(first,{'welcome_language':'ru','welcome_cycle':False,'interface_language':'ru','transformer_variant':'uc','preset':'turbo','thinking_budget':1024})==expected
  saved=token()
 finally:p.terminate();p.wait(timeout=15)
 p,second=launch()
 try:
  assert first!=second
  # The token persists, so an open browser tab keeps working across restarts.
  assert token()==saved
  assert request(second)==expected
  status=request(second,path='status')
  assert set(status['components'])>={'base','text_encoder','transformer_official','transformer_uc','turbo','pe_t2i','pe_i2i'}
  assert status['model']['components']==['base','text_encoder','transformer_uc']
  for bad in ({'interface_language':'invalid'},{'transformer_variant':'other'},{'preset':'fast'},{'thinking_budget':5},{'download_source':'huggingface'}):
   try:request(second,bad)
   except urllib.error.HTTPError as e:assert e.code==400
   else:raise AssertionError(f'Invalid preference accepted: {bad}')
 finally:p.terminate();p.wait(timeout=15)
 print('PASS: preferences and token survived changed-port relaunch; invalid values rejected.')
