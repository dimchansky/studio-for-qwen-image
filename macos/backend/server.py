"""Loopback-only backend. No model code executes in the HTTP process."""
import argparse, base64, contextlib, json, mimetypes, os, re, secrets, signal, sqlite3, subprocess, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote
import psutil
import model_store
import perf
from environment_probe import is_environment_error
from generation_options import apply_preset, plan_references, validate_options
from image_jobs import run_image_job

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('QWEN_STUDIO_DATA', str(Path.home() / 'Library/Application Support/Qwen Studio')))
MODELS = DATA / 'models'
for p in [DATA, DATA/'images', DATA/'jobs', MODELS]: p.mkdir(parents=True, exist_ok=True)

def studio_token():
    # A stable token keeps an open browser tab working across server restarts.
    if os.environ.get('QWEN_STUDIO_TOKEN'): return os.environ['QWEN_STUDIO_TOKEN']
    path=DATA/'.token'
    with contextlib.suppress(OSError):
        value=path.read_text(encoding='utf-8').strip()
        if len(value)>=32: return value
    value=secrets.token_urlsafe(32)
    path.write_text(value,encoding='utf-8');path.chmod(0o600)
    return value

TOKEN = studio_token()
DB = DATA/'sessions.sqlite3'
LOCK = threading.RLock()
JOBS = {}
ACTIVE = None
QUEUE = []
STOPPING = False
DOWNLOADS = {'process':None,'current':[],'pending':[],'error':'','samples':[]}
LANGUAGES = ('auto','zh','en','ru')

def connection():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c
with connection() as c:
    c.executescript('CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,title TEXT,created REAL,updated REAL); CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,session_id TEXT,role TEXT,content TEXT,images TEXT,meta TEXT,created REAL);')
    c.execute('CREATE TABLE IF NOT EXISTS preferences(key TEXT PRIMARY KEY,value TEXT)')

def preferences(values=None):
    defaults={'welcome_language':'zh','welcome_cycle':True,'interface_language':'auto','transformer_variant':'official','preset':'standard','thinking_budget':3072}
    with connection() as c:
        if values is not None:
            if not isinstance(values,dict) or set(values)-set(defaults): raise ValueError('未知设置。')
            for key in ('welcome_language','interface_language'):
                if key in values and values[key] not in LANGUAGES: raise ValueError('不支持的语言。')
            if 'welcome_cycle' in values and not isinstance(values['welcome_cycle'],bool): raise ValueError('轮换设置须为开关。')
            if 'transformer_variant' in values and values['transformer_variant'] not in model_store.VARIANTS: raise ValueError('未知的模型版本。')
            if 'preset' in values and values['preset'] not in ('turbo','standard','quality','custom'): raise ValueError('未知的速度模式。')
            if 'thinking_budget' in values and values['thinking_budget'] not in (1024,3072,8192,24000): raise ValueError('不支持的思考长度。')
            for key,value in values.items(): c.execute('INSERT OR REPLACE INTO preferences VALUES(?,?)',(key,json.dumps(value)))
        for row in c.execute('SELECT key,value FROM preferences'):
            if row['key'] in defaults: defaults[row['key']]=json.loads(row['value'])
    if defaults['interface_language'] not in LANGUAGES: defaults['interface_language']='auto'
    return defaults

def read_session(sid):
    with connection() as c:
        s=c.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
        if not s: raise ValueError('找不到这个会话。')
        d=dict(s);d['messages']=[dict(x) for x in c.execute('SELECT * FROM messages WHERE session_id=? ORDER BY created',(sid,))]
    for m in d['messages']:
        m['images']=json.loads(m['images']);m['meta']=json.loads(m['meta'])
    # Pair queued prompts with their eventual result before ordering the conversation.
    users={m['meta']['job_id']:m for m in d['messages'] if m['role']=='user' and m['meta'].get('job_id')}
    unmatched=[]
    for m in d['messages']:
        jid=m['meta'].get('job_id')
        if m['role']=='user' and jid:unmatched.append(jid)
        elif m['role']=='assistant':
            if not jid and unmatched:
                # Compatibility with the first queue build, which omitted result job IDs.
                jid=unmatched[0];m['meta']['job_id']=jid
            if jid in unmatched:unmatched.remove(jid)
    d['messages'].sort(key=lambda m:(users.get(m['meta'].get('job_id'),m)['created'],m['role']!='user',m['created']))
    return d

def delete_session(sid,delete_images=False):
    """Remove a chat and its job files; optionally its images that no other chat still uses."""
    with LOCK:
        if any(j['session_id']==sid and j['state'] in ('running','queued') for j in JOBS.values()): raise ValueError('请先停止这个会话中的任务。')
        with connection() as c:
            rows=c.execute('SELECT session_id,images,meta FROM messages').fetchall()
            c.execute('DELETE FROM messages WHERE session_id=?',(sid,));c.execute('DELETE FROM sessions WHERE id=?',(sid,))
        for jid in [jid for jid,j in JOBS.items() if j['session_id']==sid]: JOBS.pop(jid)
    mine=[r for r in rows if r['session_id']==sid]
    # "Continue editing" reuses a result as another chat's reference, so shared files must stay.
    elsewhere={name for r in rows if r['session_id']!=sid for name in json.loads(r['images'])}
    # Job inputs and logs contain the prompts, so they go with the chat.
    for jid in {json.loads(r['meta']).get('job_id') for r in mine}:
        if not isinstance(jid,str) or not re.fullmatch(r'[0-9A-Za-z_-]+',jid): continue
        for f in (DATA/'jobs').glob(jid+'.*'): f.unlink(missing_ok=True)
        (DATA/'images'/f'{jid}-preview.png').unlink(missing_ok=True)
    deleted=[]
    if delete_images:
        for name in sorted({name for r in mine for name in json.loads(r['images'])}-elsewhere):
            f=DATA/'images'/name
            if Path(name).name==name and f.is_file(): f.unlink();deleted.append(name)
    return {'ok':True,'deleted_images':deleted}

def message(sid,role,content,images=None,meta=None):
    with connection() as c:
        c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?)',(uuid.uuid4().hex,sid,role,content,json.dumps(images or []),json.dumps(meta or {}),time.time()))
        c.execute('UPDATE sessions SET updated=? WHERE id=?',(time.time(),sid))

# ---- Model downloads: one download.py process at a time, later requests queue behind it.

def downloading():
    process=DOWNLOADS['process']
    return process is not None and process.poll() is None

def start_next_download():
    if downloading() or STOPPING or not DOWNLOADS['pending']: return
    DOWNLOADS['current']=DOWNLOADS['pending'][:];DOWNLOADS['pending'].clear();DOWNLOADS['error']='';DOWNLOADS['samples'].clear()
    env={**os.environ,'HF_HUB_DISABLE_TELEMETRY':'1','HF_XET_CHUNK_CACHE_SIZE_BYTES':os.environ.get('HF_XET_CHUNK_CACHE_SIZE_BYTES','0'),'HF_HOME':os.environ.get('HF_HOME',str(DATA/'hf-home'))}
    with (DATA/'download.log').open('a') as log:
        DOWNLOADS['process']=subprocess.Popen([sys.executable,'-u',str(ROOT/'backend/download.py'),str(MODELS),*DOWNLOADS['current']],stdout=log,stderr=log,env=env,start_new_session=True)
    threading.Thread(target=watch_download,args=(DOWNLOADS['process'],),daemon=True).start()

def watch_download(process):
    process.wait()
    with LOCK:
        if process.returncode not in (0,-signal.SIGTERM):
            tail=''
            with contextlib.suppress(OSError):
                tail=(DATA/'download.log').read_text(encoding='utf-8',errors='replace').strip().splitlines()[-1][:300]
            DOWNLOADS['error']='下载中断。点击继续下载可重试；已完成的文件会保留。'+('\n'+tail if tail else '')
        DOWNLOADS['current']=[]
        start_next_download()

def request_download(keys):
    for key in keys:
        if key not in model_store.MANIFEST: raise ValueError('未知模型。')
    with LOCK:
        for key in keys:
            if not model_store.ready(MODELS,key) and key not in DOWNLOADS['current'] and key not in DOWNLOADS['pending']:
                DOWNLOADS['pending'].append(key)
        start_next_download()

def component_statuses():
    active=set(DOWNLOADS['current']) if downloading() else set()
    result={}
    for key in model_store.MANIFEST:
        s=model_store.status(MODELS,key)
        s.update(downloading=key in active,queued=key in DOWNLOADS['pending'])
        result[key]=s
    if active:
        # Bytes of the file in flight belong to the first unfinished active component.
        partial=model_store.partial_bytes(MODELS)
        for key in DOWNLOADS['current']:
            if not result[key]['ready']:
                result[key]['bytes']=min(result[key]['total'],result[key]['bytes']+partial);break
    return result

def aggregate(statuses,keys,path=''):
    items=[statuses[k] for k in keys]
    total=sum(x['total'] for x in items);done=sum(x['bytes'] for x in items)
    running=any(x['downloading'] or x['queued'] for x in items)
    now=time.monotonic();samples=DOWNLOADS['samples'];samples.append((now,sum(s['bytes'] for s in statuses.values())))
    while len(samples)>1 and samples[0][0]<now-15: samples.pop(0)
    elapsed=now-samples[0][0];speed=max(0,(samples[-1][1]-samples[0][1])/elapsed) if elapsed>1 else 0
    ready=all(x['ready'] for x in items)
    return {'ready':ready,'downloading':running,'bytes':done,'total':total,'speed':speed if running else 0,
            'eta':(total-done)/speed if running and speed>1024 else None,'verifying':running and done>=total and not ready,
            'path':path,'error':DOWNLOADS['error'] if not running else '','components':keys}

def system_status():
    memory=psutil.virtual_memory();swap=psutil.swap_memory()
    return {'free_disk':model_store.free_bytes(MODELS),'memory_available':memory.available,'memory_total':memory.total,'swap_used':swap.used}

def status():
    prefs=preferences();statuses=component_statuses()
    image=['base','text_encoder',model_store.VARIANTS[prefs['transformer_variant']]]
    with LOCK:
        active=JOBS.get(ACTIVE);pending=[JOBS[jid] for jid,_ in QUEUE]
        return {'model':aggregate(statuses,image,str(MODELS)),'components':statuses,
                'enhancers':{'pe-t2i':aggregate(statuses,['pe_t2i']),'pe-i2i':aggregate(statuses,['pe_i2i'])},
                'variant':prefs['transformer_variant'],'active':active,'pending':pending,'data':str(DATA),'system':system_status()}

# ---- Jobs

def run_job(job, payload):
    global ACTIVE
    sid=job['session_id']
    try:
        result=run_image_job(job,payload,ROOT,DATA,MODELS)
        message(sid,'assistant','图片已生成。',result['images'],result['meta'])
        job.update(state='done',stage='完成',progress=1)
    except InterruptedError:
        job.update(state='cancelled',stage='已停止')
        message(sid,'assistant','已停止本次任务。',meta={'cancelled':True,'job_id':job['id']})
    except Exception as e:
        diagnostic=str(e)
        log_path=DATA/'jobs'/f"{job['id']}.log"
        with contextlib.suppress(OSError):
            with log_path.open('rb') as stream:
                stream.seek(max(0,log_path.stat().st_size-16000));diagnostic+='\n'+stream.read().decode(errors='replace')
        job.update(state='error',stage='任务失败',error=str(e),environment_error=is_environment_error(diagnostic))
        message(sid,'assistant',str(e),meta={'error':True,'job_id':job['id']})
        if job.get('environment_error'):
            # A broken runtime cannot execute queued work. Keep every prompt in
            # its chat, with an explicit result, instead of repeatedly failing.
            with LOCK:
                for queued_id,_ in QUEUE:
                    queued=JOBS[queued_id];queued.update(state='cancelled',stage='已停止')
                    message(queued['session_id'],'assistant','环境缺失，排队任务已停止。',meta={'cancelled':True,'job_id':queued_id})
                QUEUE.clear()
    finally:
        with LOCK:
            ACTIVE=None
            advance_queue()

def advance_queue():
    global ACTIVE
    if ACTIVE or STOPPING or not QUEUE:return
    jid,payload=QUEUE.pop(0)
    job=JOBS[jid];ACTIVE=jid
    job.update(state='running',stage='准备中',started=time.time())
    threading.Thread(target=run_job,args=(job,payload),daemon=True).start()

def cancel_job(jid):
    with LOCK:
        job=JOBS.get(jid)
        if not job:return
        if job['state']=='queued':
            QUEUE[:]=[(key,p) for key,p in QUEUE if key!=jid]
            job.update(state='cancelled',stage='已取消排队')
            message(job['session_id'],'assistant','已取消排队。',meta={'cancelled':True,'job_id':job['id']})
        elif job['state']=='running':job.update(cancel=True,stage='正在停止')

def validate_job(p):
    """Normalise and validate a generation request in place (shared by /generate and /estimate)."""
    prefs=preferences()
    refs=p.get('images',[])
    if not isinstance(refs,list) or len(refs)>10: raise ValueError('最多使用 10 张参考图。')
    for name in refs:
        if not isinstance(name,str) or Path(name).name!=name or not (DATA/'images'/name).is_file(): raise ValueError('参考图不存在，请重新添加。')
    for key in ['width','height']:
        p[key]=int(p.get(key,1024))
        if p[key]<256 or p[key]>2752 or p[key]%32: raise ValueError('图片尺寸须为 256–2752 之间的 32 的倍数。')
    if p['width']*p['height']>4_300_800: raise ValueError('图片总像素暂不超过约 430 万，请选择支持的 2K 尺寸。')
    p['seed']=int(p.get('seed',-1))
    if p['seed'] < -1 or p['seed']>2**32-1: raise ValueError('种子须为 -1 或 0–4294967295。')
    p.setdefault('enhance',False);p.setdefault('ratio_mode','fixed')
    validate_options(p)
    p['steps']=int(p.get('steps',25))
    if not 1<=p['steps']<=60: raise ValueError('步数须为 1–60。')
    apply_preset(p)
    p['variant']=p.get('variant') or prefs['transformer_variant']
    if p['variant'] not in model_store.VARIANTS: raise ValueError('未知的模型版本。')
    p['use_kv_cache']=bool(p.get('use_kv_cache',True))
    p['previews']=bool(p.get('previews',True))
    p['thinking_budget']=int(p.get('thinking_budget') or prefs['thinking_budget'])
    return p

def missing_components(p):
    task=('edit' if p.get('images') else 't2i') if p.get('enhance') else None
    keys=model_store.required_components(p['variant'],p['turbo'],task)
    return [model_store.MANIFEST[k]['label'] for k in keys if not model_store.ready(MODELS,k)]

def start_job(p):
    prompt=str(p.get('prompt','')).strip()
    if not prompt or len(prompt)>16000: raise ValueError('请输入 1–16000 字的内容。')
    read_session(p['session_id'])
    p['mode']='image'
    validate_job(p)
    missing=missing_components(p)
    if missing: raise ValueError('请先在“模型设置”中下载：'+'、'.join(missing))
    refs=p.get('images',[])
    with LOCK:
        if STOPPING: raise ValueError('应用正在关闭，请重新打开后发送。')
        if len(QUEUE)>=10: raise ValueError('已有 10 条消息排队，请稍后再发送。')
        jid=uuid.uuid4().hex
        job={'id':jid,'session_id':p['session_id'],'state':'queued','stage':'等待前一个任务完成','progress':0,'text':'','started':time.time(),'mode':'image','width':p['width'],'height':p['height']}
        JOBS[jid]=job
        p['prompt']=prompt
        message(p['session_id'],'user',prompt,refs,{'mode':'image','job_id':jid,'preset':p.get('preset'),'variant':p['variant']})
        with connection() as c:
            c.execute("UPDATE sessions SET title=? WHERE id=? AND title IN ('新会话','New chat','Новый чат')",(prompt[:28],p['session_id']))
        QUEUE.append((jid,p.copy()))
        advance_queue()
    return job

def estimate(p):
    validate_job(p)
    refs=len(p.get('images',[]))
    side,cache=plan_references(refs,p['width'],p['height'],float(os.environ.get('QWEN_STUDIO_KV_BUDGET_GB','6')))
    result=perf.estimate(DATA,width=p['width'],height=p['height'],steps=p['steps'],count=p.get('count',1),references=refs,
        reference_side=side,cfg=p.get('cfg',1),enhance=p.get('enhance',False),dtype=os.environ.get('QWEN_STUDIO_DTYPE','auto').replace('auto','fp16'))
    result.update(reference_resolution=side,kv_cache_gb=cache,missing=missing_components(p),steps=p['steps'],turbo=p['turbo'])
    return result

def diagnostics():
    from environment_probe import collect
    return list(collect(DATA))

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def send_json(self,data,code=200):
        raw=json.dumps(data,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
    def authorized(self):
        host=self.headers.get('Host','').split(':')[0]
        if host not in ('127.0.0.1','localhost'): return False
        if self.path.startswith('/api/'):
            return secrets.compare_digest(self.headers.get('X-Studio-Token',''),TOKEN)
        return True
    def do_GET(self):
        if not self.authorized(): return self.send_json({'error':'Unauthorized'},403)
        path=unquote(urlparse(self.path).path)
        try:
            if path=='/api/status': return self.send_json(status())
            if path=='/api/preferences': return self.send_json(preferences())
            if path=='/api/sessions':
                with connection() as c: return self.send_json([dict(x) for x in c.execute('SELECT * FROM sessions ORDER BY updated DESC')])
            if path.startswith('/api/sessions/'): return self.send_json(read_session(path.split('/')[-1]))
            if path.startswith('/api/jobs/'):
                j=JOBS.get(path.split('/')[-1])
                if not j: raise ValueError('任务已结束或程序已重启。')
                return self.send_json(j)
            if path=='/api/gallery':
                with connection() as c: rows=c.execute("SELECT images,meta,created FROM messages WHERE role='assistant' ORDER BY created DESC").fetchall()
                return self.send_json([{'image':im,'meta':json.loads(r['meta']),'created':r['created']} for r in rows for im in json.loads(r['images'])])
            if path.startswith('/media/'):
                name=path.removeprefix('/media/')
                if Path(name).name!=name: raise ValueError('Invalid path')
                f=DATA/'images'/name
            else:
                rel='index.html' if path=='/' else path.lstrip('/')
                f=(ROOT/'web'/rel).resolve()
                if not f.is_relative_to((ROOT/'web').resolve()): raise ValueError('Invalid path')
            if not f.is_file(): return self.send_json({'error':'Not found'},404)
            raw=f.read_bytes()
            if f.name=='index.html': raw=raw.replace(b'__STUDIO_TOKEN__',TOKEN.encode()).replace(b'__STUDIO_LANGUAGE__',preferences()['interface_language'].encode())
            self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(str(f))[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(raw)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data: blob:; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'");self.end_headers();self.wfile.write(raw)
        except (ValueError,KeyError) as e: self.send_json({'error':str(e),'environment_error':is_environment_error(e)},400)
        except Exception as e: self.send_json({'error':str(e),'environment_error':is_environment_error(e)},500)
    def do_POST(self):
        if not self.authorized(): return self.send_json({'error':'Unauthorized'},403)
        try:
            length=int(self.headers.get('Content-Length',0))
            if length>30*1024*1024: raise ValueError('文件过大，请使用小于 20 MB 的图片。')
            p=json.loads(self.rfile.read(length) or '{}');path=urlparse(self.path).path
            if path=='/api/preferences': return self.send_json(preferences(p))
            if path=='/api/sessions':
                sid=uuid.uuid4().hex
                title={'en':'New chat','ru':'Новый чат'}.get(self.headers.get('X-Studio-Language'),'新会话')
                with connection() as c: c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(sid,title,time.time(),time.time()))
                return self.send_json(read_session(sid))
            if path=='/api/session/delete': return self.send_json(delete_session(str(p['id']),p.get('delete_images') is True))
            if path=='/api/session/rename':
                title=str(p['title']).strip()[:80]
                if not title: raise ValueError('名称不能为空。')
                with connection() as c: c.execute('UPDATE sessions SET title=? WHERE id=?',(title,p['id']))
                return self.send_json({'ok':True})
            if path=='/api/upload':
                from PIL import Image, ImageOps
                import io
                raw=base64.b64decode(p['data'],validate=True)
                if len(raw)>20*1024*1024: raise ValueError('图片应小于 20 MB。')
                im=Image.open(io.BytesIO(raw))
                if im.width*im.height>25_000_000: raise ValueError('图片请限制在 2500 万像素以内。')
                im.load();im=ImageOps.exif_transpose(im)
                im=im.convert('RGBA' if 'A' in im.getbands() or 'transparency' in im.info else 'RGB')
                name=uuid.uuid4().hex+'.png';im.save(DATA/'images'/name)
                return self.send_json({'image':name})
            if path=='/api/generate': return self.send_json(start_job(p))
            if path=='/api/estimate': return self.send_json(estimate(p))
            if path=='/api/cancel':
                cancel_job(p['id'])
                return self.send_json({'ok':True})
            if path=='/api/model/download':
                keys=p.get('components') or []
                if not isinstance(keys,list) or not keys: raise ValueError('请选择要下载的模型。')
                request_download(keys)
                return self.send_json(status())
            if path=='/api/reveal':
                subprocess.run(['/usr/bin/open',str(DATA)],check=False)
                return self.send_json({'ok':True})
            if path=='/api/diagnostics': return self.send_json(diagnostics())
            return self.send_json({'error':'Not found'},404)
        except (ValueError,KeyError,TypeError) as e: self.send_json({'error':str(e),'environment_error':is_environment_error(e)},400)
        except Exception as e: self.send_json({'error':str(e),'environment_error':is_environment_error(e)},500)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=0);args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(json.dumps({'port':server.server_port,'pid':os.getpid()}),flush=True)
    def stop(*_):
        global STOPPING
        with LOCK:
            STOPPING=True
            for jid,_payload in QUEUE[:]:cancel_job(jid)
            if ACTIVE: JOBS[ACTIVE]['cancel']=True
            DOWNLOADS['pending'].clear()
        if downloading(): os.killpg(DOWNLOADS['process'].pid,signal.SIGTERM)
        threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    server.serve_forever()
    deadline=time.time()+10
    while ACTIVE and time.time()<deadline: time.sleep(.2)
