"""Selectable official sources, resumable parallel downloads and SHA-256 checks."""
import concurrent.futures, fcntl, hashlib, json, os, subprocess, sys
from pathlib import Path
from model_sources import download_url, validate_source
source=validate_source(sys.argv[2] if len(sys.argv)>2 else 'modelscope')
root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True)
lock=(root/'.download.lock').open('w')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:print('Download already running',flush=True);sys.exit(0)
(root/'.download.pid').write_text(str(os.getpid()))
(root/'.download-source').write_text(source)
target=sys.argv[3] if len(sys.argv)>3 else 'image'
if target not in ('image','pe-t2i','pe-i2i'):raise ValueError('Unknown model target')
files=json.loads(Path(__file__).with_name('model-files.json' if target=='image' else target+'-files.json').read_text())
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def url(item):return download_url(item,source)
def chunk_download(task):
 item,start,end,path=task;size=end-start+1
 tmp=Path(str(path)+'.receiving')
 for attempt in range(6):
  # Preserve a partial network response from an interrupted process before resuming.
  if tmp.exists():
   previous=path.stat().st_size if path.exists() else 0
   if previous+tmp.stat().st_size<=size:
    with path.open('ab') as out,tmp.open('rb') as src:
     for b in iter(lambda:src.read(8*1024*1024),b''):out.write(b)
   tmp.unlink()
  offset=path.stat().st_size if path.exists() else 0
  if offset==size:return
  if offset>size:path.unlink();offset=0
  result=subprocess.run(['/usr/bin/curl','--fail','--location','--connect-timeout','20','--max-time','900','--range',f'{start+offset}-{end}','--output',str(tmp),'--silent','--show-error',url(item)])
  if result.returncode==0 and tmp.stat().st_size!=size-offset:
   tmp.unlink();raise RuntimeError('下载源未正确返回文件分段。请重试。')
 # Retain partial responses for the next resume.
 raise RuntimeError('分段下载暂时失败，请点击继续下载重试。')
plans=[];tasks=[]
for item in files:
 dest=root/item['path'];dest.parent.mkdir(parents=True,exist_ok=True)
 if dest.exists() and dest.stat().st_size==item['size'] and digest(dest)==item['sha256']:
  print('Verified',item['path'],flush=True);continue
 part=dest.with_suffix(dest.suffix+'.part');offset=part.stat().st_size if part.exists() else 0
 if offset>item['size']:part.unlink();offset=0
 chunks=[]
 for start in range(offset,item['size'],128*1024*1024):
  end=min(start+128*1024*1024,item['size'])-1
  path=dest.with_name(dest.name+f'.chunk-{start}-{end}')
  tasks.append((item,start,end,path));chunks.append(path)
 plans.append((item,dest,part,chunks))
try:
 with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:list(pool.map(chunk_download,tasks))
 for item,dest,part,chunks in plans:
  assembled=dest.with_suffix(dest.suffix+'.assembling')
  sources=([part] if part.exists() else [])+chunks
  with assembled.open('wb') as out:
   for ch in sources:
    with ch.open('rb') as src:
     for b in iter(lambda:src.read(8*1024*1024),b''):out.write(b)
  if assembled.stat().st_size!=item['size'] or digest(assembled)!=item['sha256']:
   assembled.unlink(missing_ok=True);part.unlink(missing_ok=True)
   for ch in chunks:ch.unlink(missing_ok=True)
   raise RuntimeError('校验失败，请重试：'+item['path'])
  assembled.replace(dest)
  for ch in sources:ch.unlink(missing_ok=True)
  print('Completed',item['path'],flush=True)
 (root/'.verified').write_text(f'{source}: all official model files SHA-256 verified\n')
 print('Model ready',flush=True)
finally:
 (root/'.download.pid').unlink(missing_ok=True)
 lock.close()
