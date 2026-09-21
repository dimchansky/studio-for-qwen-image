"""Preferences survive two actual backend launches with different loopback origins."""
import json,os,subprocess,sys,tempfile,urllib.request,urllib.error
from pathlib import Path
server=Path(__file__).resolve().parents[1]/'backend/server.py'
with tempfile.TemporaryDirectory() as data:
 env={**os.environ,'QWEN_STUDIO_DATA':data,'QWEN_STUDIO_TOKEN':'preferences-test','PYTHONUNBUFFERED':'1'}
 def launch():
  p=subprocess.Popen([sys.executable,str(server)],env=env,stdout=subprocess.PIPE,text=True)
  port=json.loads(p.stdout.readline())['port']
  return p,port
 def request(port,body=None):
  req=urllib.request.Request(f'http://127.0.0.1:{port}/api/preferences',data=None if body is None else json.dumps(body).encode(),headers={'X-Studio-Token':'preferences-test','Content-Type':'application/json'})
  with urllib.request.urlopen(req) as response:return json.load(response)
 p,first=launch()
 try:
  assert request(first)['download_source'] is None
  assert request(first,{'welcome_language':'en','welcome_cycle':False,'download_source':'huggingface','interface_language':'en'})=={'welcome_language':'en','welcome_cycle':False,'download_source':'huggingface','interface_language':'en'}
 finally:p.terminate();p.wait(timeout=15)
 p,second=launch()
 try:
  assert first!=second
  assert request(second)=={'welcome_language':'en','welcome_cycle':False,'download_source':'huggingface','interface_language':'en'}
  assert Path(data,'ui-language.txt').read_text()=='en'
  Path(data,'ui-language.txt').write_text('zh')
  assert request(second)['interface_language']=='zh'
  try:request(second,{'interface_language':'invalid'})
  except urllib.error.HTTPError as e:assert e.code==400
  else:raise AssertionError('Invalid preference accepted')
  try:request(second,{'download_source':'untrusted'})
  except urllib.error.HTTPError as e:assert e.code==400
  else:raise AssertionError('Unknown download source accepted')
 finally:p.terminate();p.wait(timeout=15)
 print('PASS: preferences survived changed-port relaunch; invalid values rejected.')
