"""Isolated Ollama stream, so Stop can also cancel model loading / stalled replies."""
import json, sys
from pathlib import Path
from io_utils import atomic_json
from urllib.request import Request, build_opener, ProxyHandler
p=json.loads(Path(sys.argv[1]).read_text());status=Path(p['status_path']);text=''
def report(**state):
 atomic_json(status,state)
try:
 body={'model':p['chat_model'],'messages':p['history'],'stream':True,'keep_alive':0,'options':{'num_ctx':4096}}
 if p.get('think') is not None:body['think']=p['think']
 req=Request('http://127.0.0.1:11434/api/chat',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 report(stage='正在加载聊天模型',text='',progress=None)
 with build_opener(ProxyHandler({})).open(req,timeout=300) as r:
  for raw in r:
   item=json.loads(raw)
   if item.get('error'):raise RuntimeError(item['error'])
   text+=item.get('message',{}).get('content','')
   report(stage='正在回复' if text else '正在思考',text=text,progress=None)
 if not text.strip():raise RuntimeError('模型没有返回正文，请重试或更换聊天模型。')
 report(stage='完成',text=text,progress=1)
except Exception as e:
 report(error=str(e),stage='聊天失败');sys.exit(1)
