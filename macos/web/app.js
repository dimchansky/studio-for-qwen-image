const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const paths={model:'M12 3 3 8v8l9 5 9-5V8zM3 8l9 5 9-5M12 13v8',chevron:'M8 10l4 4 4-4',check:'M5 12l4 4L19 6',plus:'M12 5v14M5 12h14',panel:'M9 3v18M4 3h16v18H4z',search:'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',image:'M3 3h18v18H3zM3 16l5-5 5 5 4-4 4 4M8 7h.01',sliders:'M4 7h7m4 0h5M4 17h3m4 0h9M11 4v6m-4 4v6',arrow:'M12 19V5m-6 6 6-6 6 6','arrow-right':'M4 12h16m-6-6 6 6-6 6',close:'M6 6l12 12M6 18 18 6',layers:'M12 3 2 8l10 5 10-5zM2 12l10 5 10-5M2 16l10 5 10-5',folder:'M3 6h7l2 3h9v11H3z',more:'M5 12h.01M12 12h.01M19 12h.01',download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',stop:'M6 6h12v12H6z',sparkles:'M11 3l1.8 4.9L17.7 9.7l-4.9 1.8L11 16.4l-1.8-4.9L4.3 9.7l4.9-1.8zM18.5 14.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z',trash:'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6',template:'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z'};
function icon(name){const s=document.createElementNS('http://www.w3.org/2000/svg','svg');s.setAttribute('viewBox','0 0 24 24');s.setAttribute('aria-hidden','true');const p=document.createElementNS(s.namespaceURI,'path');p.setAttribute('d',paths[name]||paths.image);s.append(p);return s}
function icons(root=document){root.querySelectorAll('[data-icon]').forEach(e=>{const i=icon(e.dataset.icon);if(e.tagName==='I')e.replaceWith(i);else e.replaceChildren(i)})}icons();
let session=null,sessions=[],attachments=[],job=null,lastStatus=null,polling=false,pageName='workspace',submitting=false,pendingJobs=[],enhanceJob=null,enhanceUndo=null,enhancePolling=false;
let variant='official',preset='standard';
const PRESET_STEPS={turbo:4,standard:25,quality:40};
const token=$('meta[name=studio-token]').content;
async function api(path,body){const r=await fetch('/api/'+path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-Studio-Token':token,'X-Studio-Language':StudioI18n.locale()},body:body===undefined?undefined:JSON.stringify(body)});const data=await r.json();if(!r.ok){if(data.environment_error)openDiagnostics();throw Error(data.error||'请求失败');}return data}
let toastTimer;function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,6000)}
function safe(fn){return (...args)=>Promise.resolve().then(()=>fn(...args)).catch(e=>toast(e.message))}
const reduceMotion=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
function motion(el,frames,duration=240){if(!el||reduceMotion())return;el.getAnimations().forEach(a=>a.cancel());return el.animate(frames,{duration,easing:'cubic-bezier(.16,1,.3,1)'});}
function showPage(name){
 closeCreation();pageName=name;syncWelcome();
 for(const id of ['workspace','gallery','settings']){const el=$('#'+id);el.hidden=id!==name;}
 motion($('#'+name),[{opacity:.25,filter:'blur(3px)',transform:'translateY(7px)'},{opacity:1,filter:'blur(0px)',transform:'translateY(0)'}]);
 $$('.nav-item').forEach(b=>b.classList.toggle('selected',(name==='workspace'&&b.id==='new-session')||(name==='gallery'&&b.id==='gallery-button')||(name==='settings'&&b.id==='settings-button')));
}
// Kept for callers that switch the composer into image editing (annotation, gallery).
function setMode(){$('#prompt').placeholder=attachments.length?'描述修改内容…':'描述画面，或添加图片…';updateSend()}
function updateSend(){const empty=!$('#prompt').value.trim();$('#send').disabled=$('#enhance-now').disabled=empty||submitting||!!enhanceJob;const label=submitting?'正在发送':job?'加入队列':'生成图片';$('#send').setAttribute('aria-label',label);$('#send').title=label}
function renderSessions(){const q=$('#search').value.toLowerCase();$('#sessions').replaceChildren();sessions.filter(s=>s.title.toLowerCase().includes(q)).forEach(s=>{const row=document.createElement('div');row.className='session-row';const b=document.createElement('button');b.className='session'+(session?.id===s.id?' current':'');b.setAttribute('translate','no');b.textContent=s.title;b.title=s.title;b.onclick=safe(()=>loadSession(s.id));const remove=document.createElement('button');remove.type='button';remove.className='icon-button session-delete';remove.setAttribute('aria-label','删除会话');remove.title='删除会话';remove.append(icon('trash'));remove.onclick=()=>askDeleteSession(s);row.append(b,remove);$('#sessions').append(row)});if(!$('#sessions').children.length){const e=document.createElement('div');e.className='history-empty';e.textContent=q?'没有找到匹配的会话':'暂无会话';$('#sessions').append(e)}}
async function refreshSessions(){sessions=await api('sessions');renderSessions()}
async function loadSession(id){session=await api('sessions/'+id);attachments=[];renderAttachments();showPage('workspace');renderSession();renderSessions()}
function reset(){session=null;attachments=[];$('#prompt').value='';renderAttachments();showPage('workspace');renderSession();renderSessions();$('#prompt').focus();enhanceUndo=null;renderEnhance();updateSend()}
function imageElement(name){const img=document.createElement('img');img.src='/media/'+encodeURIComponent(name);img.alt='会话中的图片';img.className='result-image';img.loading='lazy';img.tabIndex=0;img.setAttribute('role','button');img.setAttribute('aria-label','查看大图');img.onclick=()=>openImage(name);img.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openImage(name)}};return img}
let viewingImage=null;
function openImage(name){viewingImage=name;$('#viewer-image').src='/media/'+encodeURIComponent(name);$('.viewer-canvas').classList.remove('zoomed');$('#viewer-zoom').textContent='原始尺寸';$('#image-viewer').showModal()}
function toggleImageZoom(){const zoomed=$('.viewer-canvas').classList.toggle('zoomed');$('#viewer-zoom').textContent=zoomed?'适应窗口':'原始尺寸'}
$('#viewer-image').onclick=$('#viewer-zoom').onclick=toggleImageZoom;
function saveImage(name){const a=document.createElement('a');a.href='/media/'+encodeURIComponent(name);a.download='Qwen-'+name;document.body.append(a);a.click();a.remove()}
$('#viewer-save').onclick=()=>{if(viewingImage)saveImage(viewingImage)};
$('#viewer-use').onclick=()=>{if(viewingImage){$('#image-viewer').close();useImage(viewingImage)}};
function useImage(name){showPage('workspace');if(attachments.length>=10)return toast('最多添加 10 张参考图');if(!attachments.includes(name))attachments.push(name);renderAttachments();$('#prompt').focus()}
function imageButtons(name){const row=document.createElement('div');row.className='image-actions';const edit=document.createElement('button');edit.className='text-button';edit.append(icon('layers'),document.createTextNode('继续修改'));edit.onclick=()=>useImage(name);const save=document.createElement('button');save.className='text-button';save.append(icon('download'),document.createTextNode('保存图片'));save.onclick=()=>saveImage(name);row.append(edit,save);return row}
let messagesFollowEnd=true,scrollEndFrame=null;
function scrollMessagesToEnd(){cancelAnimationFrame(scrollEndFrame);scrollEndFrame=requestAnimationFrame(()=>{const list=$('#messages');list.scrollTop=list.scrollHeight;messagesFollowEnd=true})}
$('#messages').addEventListener('scroll',()=>{const list=$('#messages');messagesFollowEnd=list.scrollHeight-list.scrollTop-list.clientHeight<48},{passive:true});
new ResizeObserver(()=>{if(messagesFollowEnd)scrollMessagesToEnd()}).observe($('#messages'));
function imageSummary(meta){const parts=[`${meta.width} × ${meta.height}　${meta.steps} 步　${meta.seconds} 秒`];return parts.join('')}
function renderSession(){const before=$('#composer-area').getBoundingClientRect();const wasEmpty=$('#workspace').classList.contains('empty');const empty=!session?.messages.length;$('#workspace').classList.toggle('empty',empty);$('#welcome').hidden=!empty;syncWelcome();$('#thread-title').setAttribute('translate',session?'no':'yes');$('#thread-title').textContent=session?.title||'新会话';$('#session-menu').hidden=!session;const list=$('#messages');list.replaceChildren();(session?.messages||[]).forEach(m=>{const el=document.createElement('article');el.className='message '+m.role+(m.meta.error?' error':'');const role=document.createElement('div');role.className='role';if(m.role!=='user')role.setAttribute('translate','no');role.textContent=m.role==='user'?'你':'Qwen-Image-2.1'+(m.meta.variant==='uc'?' · UC':'')+(m.meta.turbo?' · Turbo':'');el.append(role);if(m.content){const c=document.createElement('div');c.className='content';if(m.role==='user'||(!m.meta.error&&!m.meta.cancelled&&!(m.meta.mode==='image'&&m.images.length)))c.setAttribute('translate','no');c.textContent=m.content;el.append(c)}if(m.images.length){const imgs=document.createElement('div');imgs.className='message-images';m.images.forEach(name=>{const figure=document.createElement('figure');figure.append(imageElement(name));if(m.role==='assistant')figure.append(imageButtons(name));imgs.append(figure)});el.append(imgs);if(m.role==='assistant'){const meta=document.createElement('div');meta.className='image-meta';meta.textContent=imageSummary(m.meta);el.append(meta);if(m.meta.effective_prompt)el.append(promptDetails(m.meta))}}else if(m.role==='assistant'&&m.meta.enhanced_prompt)el.append(promptDetails(m.meta));list.append(el)});messagesFollowEnd=true;renderJob();renderTaskTray();scrollMessagesToEnd();if(wasEmpty!==empty&&pageName==='workspace'){const after=$('#composer-area').getBoundingClientRect();motion($('#composer-area'),[{transform:`translate(${before.left-after.left}px,${before.top-after.top}px)`},{transform:'translate(0,0)'}],420);motion(list,[{opacity:0},{opacity:1}],300)}}
let taskTrayOpen=false,taskTrayTimer=null,taskTrayFrame=null;
function setTaskTrayVisible(visible){
 if(visible===taskTrayOpen)return;
 taskTrayOpen=visible;clearTimeout(taskTrayTimer);cancelAnimationFrame(taskTrayFrame);
 const tray=$('#task-tray');tray.inert=!visible;
 if(visible){tray.hidden=false;taskTrayFrame=requestAnimationFrame(()=>{taskTrayFrame=requestAnimationFrame(()=>{if(taskTrayOpen)tray.classList.add('is-open')})})}
 else{if(tray.contains(document.activeElement))$('#prompt').focus({preventScroll:true});tray.classList.remove('is-open');taskTrayTimer=setTimeout(()=>{if(!taskTrayOpen)tray.hidden=true},reduceMotion()?100:280)}
}
function jobStage(item){let text=t(item.stage||'');if(item.pe_phase&&item.stage==='正在增强提示词')text+=` · ${item.pe_tokens||0} tok · ${item.pe_tps||0} tok/s`;return text}
function renderTaskTray(){
 const active=lastStatus?.active;
 const visible=!!active||pendingJobs.length>0;
 setTaskTrayVisible(visible);
 if(!visible)return;
 const running=$('#running-task');running.replaceChildren();
 if(active){const text=document.createElement('span');text.textContent=active.mode==='enhance'?t('提示词增强：')+jobStage(active):(active.session_id===session?.id?'':t('其他会话：'))+jobStage(active);const view=document.createElement('button');view.type='button';view.textContent='查看';view.onclick=safe(()=>loadSession(active.session_id));const stop=document.createElement('button');stop.type='button';stop.className='danger-button';stop.textContent='停止';stop.onclick=safe(async()=>{await api('cancel',{id:active.id});await refreshStatus()});running.append(...(active.mode==='enhance'?[text,stop]:[text,view,stop]))}
 $('#queued-tasks').replaceChildren(...pendingJobs.map((item,i)=>{const row=document.createElement('div');const text=document.createElement('button');text.type='button';const enhance=item.mode==='enhance';text.textContent=enhance?`等待中 ${i+1}：提示词增强`:`等待中 ${i+1}：${sessions.find(s=>s.id===item.session_id)?.title||'新会话'}`;text.onclick=enhance?()=>$('#prompt').focus():safe(()=>loadSession(item.session_id));const cancel=document.createElement('button');cancel.type='button';cancel.className='danger-button';cancel.textContent='取消';cancel.onclick=safe(async()=>{await api('cancel',{id:item.id});await refreshStatus();if(session?.id===item.session_id){session=await api('sessions/'+session.id);renderSession()}});row.append(text,cancel);return row}));
}
// The enhancer finishes minutes before the image: show its rewrite as soon as it exists.
function renderLivePrompt(el){let live=el.querySelector('.live-prompt');if(!job.enhanced_prompt){live?.remove();return}if(!live){live=document.createElement('details');live.className='prompt-details live-prompt';live.open=true;const summary=document.createElement('summary');summary.textContent='增强提示词';const body=document.createElement('p');body.className='prompt-value';body.setAttribute('translate','no');live.append(summary,body);el.insertBefore(live,el.querySelector('.generation-canvas'))}const body=live.querySelector('.prompt-value');if(body.textContent!==job.enhanced_prompt)body.textContent=job.enhanced_prompt}
function renderJob(){const follow=messagesFollowEnd;let el=$('#active-job');if(!job||job.session_id!==session?.id){el?.remove();return}if(el&&el.dataset.job!==job.id){el.remove();el=null}if(!el){el=document.createElement('article');el.dataset.job=job.id;el.id='active-job';el.className='message';const role=document.createElement('div');role.className='role';role.setAttribute('translate','no');role.textContent='Qwen-Image-2.1';const content=document.createElement('div');content.className='content';content.setAttribute('translate','no');const state=document.createElement('div');state.className='job-state';const stage=document.createElement('span');stage.className='stage';const progress=document.createElement('progress');progress.max=1;const stop=document.createElement('button');stop.className='text-button danger-button';stop.append(icon('stop'),document.createTextNode('停止'));stop.onclick=safe(async()=>{await api('cancel',{id:job.id});stop.disabled=true;stage.textContent=t('正在停止…')});state.append(stage,progress,stop);el.append(role,content);const canvas=document.createElement('div');canvas.className='generation-canvas';canvas.style.aspectRatio=(job.width||1)+' / '+(job.height||1);canvas.style.setProperty('--preview-ratio',(job.width||1)/(job.height||1));const preview=document.createElement('img');preview.alt='低分辨率生成预览';preview.className='generation-preview';const caption=document.createElement('span');caption.className='generation-caption';caption.textContent='正在构图';canvas.append(preview,caption);el.append(canvas);el.append(state);$('#messages').append(el)}el.querySelector('.content').textContent=job.text||'';el.querySelector('.stage').textContent=jobStage(job);renderLivePrompt(el);const pr=el.querySelector('progress');if(job.progress==null)pr.removeAttribute('value');else pr.value=job.progress;const canvas=el.querySelector('.generation-canvas');if(canvas){canvas.style.aspectRatio=(job.width||1)+' / '+(job.height||1);canvas.style.setProperty('--preview-ratio',(job.width||1)/(job.height||1))}if(canvas&&job.preview&&canvas.dataset.step!==String(job.preview_step)){canvas.dataset.step=job.preview_step;const img=canvas.querySelector('img');img.onload=()=>{canvas.classList.add('has-preview');img.style.filter=`blur(${Math.max(0,5*(1-(job.progress||0)))}px)`};img.src='/media/'+encodeURIComponent(job.preview)+'?step='+job.preview_step;canvas.querySelector('.generation-caption').textContent='生成预览';}if(follow)scrollMessagesToEnd();}
async function pollJob(){if(!job||polling)return;polling=true;try{const latest=await api('jobs/'+job.id);job=latest;if(job.state!=='running'){const sid=job.session_id;if(job.state==='error')toast(job.error);const environmentError=job.environment_error;job=null;if(session?.id===sid){session=await api('sessions/'+sid);renderSession()}await refreshSessions();updateSend();await refreshStatus();if(environmentError)openDiagnostics()}else renderJob()}catch(e){toast(e.message);job=null;updateSend()}finally{polling=false}}
$('#composer').onsubmit=safe(async e=>{
 e.preventDefault();if(submitting||enhanceJob)return;
 const prompt=$('#prompt').value.trim();if(!prompt)return;
 const missing=missingComponents();
 if(missing.length){showPage('settings');return toast(t('请先在“模型设置”中下载：')+missing.map(key=>t(COMPONENT_TITLES[key]||key)).join(t('、')))}
 submitting=true;updateSend();
 try{
  if(!session)session=await api('sessions',{});
  const sid=session.id,submittedText=$('#prompt').value;
  const created=await api('generate',{session_id:sid,prompt,images:attachments,...generationOptions()});enhanceUndo=null;renderEnhance();
  if(session?.id===sid){if($('#prompt').value===submittedText)$('#prompt').value='';attachments=[];renderAttachments();session=await api('sessions/'+sid);renderSession()}
  if(created.state==='running')job=created;
  if(created.state==='queued')toast('已加入队列，前一个任务完成后自动发送');
  await refreshSessions();await refreshStatus();renderJob();
 }finally{submitting=false;updateSend()}
});
// Enhance only: the rewrite replaces the prompt, so the next image can be made without the enhancer.
function renderEnhance(note){const busy=!!enhanceJob;$('#prompt').readOnly=busy;$('#composer').classList.toggle('enhancing',busy);$('#enhance-status').hidden=!busy&&!note;$('#enhance-text').textContent=busy?jobStage(enhanceJob):note||'';$('#enhance-stop').hidden=!busy;$('#enhance-undo').hidden=busy||!enhanceUndo}
function selectSize(width,height){const value=width+','+height,select=$('#size');if(![...select.options].some(o=>o.value===value)){let group=select.querySelector('optgroup[data-extra]');if(!group){group=document.createElement('optgroup');group.dataset.extra='';group.label='其他尺寸';select.append(group)}const option=document.createElement('option');option.value=value;option.textContent=`${width} × ${height}`;group.append(option)}select.value=value;syncSizeLabel()}
function applyEnhancement(result){
 $('#prompt').value=result.prompt;
 // Enhancing again at send time would rewrite the rewrite.
 if(enhanceOn())syncEnhance(false);
 const [width,height]=currentSize();let note='提示词已增强。';
 if(enhanceUndo?.ratio==='auto'){$('#ratio-mode').value='fixed';if(result.width!==width||result.height!==height){selectSize(result.width,result.height);note=`提示词已增强，图片尺寸改为 ${result.width} × ${result.height}。`}}
 renderEnhance(note);updateSend();syncWelcome();scheduleEstimate();$('#prompt').focus();
}
async function pollEnhance(){
 if(!enhanceJob||enhancePolling)return;enhancePolling=true;
 try{
  const latest=await api('jobs/'+enhanceJob.id);
  if(latest.state==='queued'||latest.state==='running'){enhanceJob=latest;renderEnhance();return}
  enhanceJob=null;
  if(latest.state==='done')return applyEnhancement(latest.result);
  enhanceUndo=null;renderEnhance();toast(latest.state==='error'?latest.error:'已停止提示词增强');
 }catch(e){enhanceJob=null;enhanceUndo=null;renderEnhance();toast(e.message)}
 finally{enhancePolling=false;updateSend()}
}
$('#enhance-now').onclick=safe(async()=>{
 const prompt=$('#prompt').value.trim();if(!prompt||enhanceJob||submitting)return;
 const key=attachments.length?'pe_i2i':'pe_t2i';
 if(lastStatus?.components&&!lastStatus.components[key]?.ready){showPage('settings');return toast(t('请先在“模型设置”中下载：')+t(COMPONENT_TITLES[key]))}
 const o=generationOptions(),undo={text:$('#prompt').value,size:$('#size').value,ratio:o.ratio_mode,enhance:o.enhance};
 $('#enhance-now').disabled=true;
 try{enhanceJob=await api('enhance',{prompt,images:attachments,width:o.width,height:o.height,ratio_mode:o.ratio_mode,exact_text:o.exact_text,transparent:o.transparent,thinking_budget:o.thinking_budget});enhanceUndo=undo}
 finally{renderEnhance();updateSend()}
 refreshStatus().catch(()=>{});
});
$('#enhance-stop').onclick=safe(async()=>{if(enhanceJob)await api('cancel',{id:enhanceJob.id})});
$('#enhance-undo').onclick=()=>{const u=enhanceUndo;if(!u)return;$('#prompt').value=u.text;syncEnhance(u.enhance);$('#size').value=u.size;$('#ratio-mode').value=u.ratio;syncSizeLabel();enhanceUndo=null;renderEnhance();updateSend();syncWelcome();scheduleEstimate();$('#prompt').focus()};
// Prevent the native submit before the async error boundary runs.
$('#composer').addEventListener('submit',e=>e.preventDefault());
$('#prompt').oninput=()=>{updateSend();syncWelcome()};$('#prompt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('#composer').requestSubmit()}};
$('#new-session').onclick=reset;$('#back').onclick=()=>{showPage('workspace')};
$('#search-button').onclick=()=>{$('#search').hidden=!$('#search').hidden;if(!$('#search').hidden)$('#search').focus()};$('#search').oninput=renderSessions;
function toggleSidebar(){const collapsed=$('#app').classList.toggle('sidebar-hidden');$('#sidebar').inert=collapsed;$('#expand').hidden=!collapsed;(collapsed?$('#expand'):$('#collapse')).focus()}
$('#collapse').onclick=$('#expand').onclick=toggleSidebar;
$('#settings-button').onclick=$('#model-status').onclick=()=>{showPage('settings');refreshStatus().catch(e=>toast(e.message))};
$$('.close-dialog').forEach(b=>b.onclick=()=>b.closest('dialog').close());$$('dialog').forEach(d=>d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close()}}));
$('#close-settings').onclick=()=>showPage('workspace');
function openOptions(){const d=$('#options');d.showModal();motion(d,[{opacity:0,transform:'translateY(8px) scale(.98)'},{opacity:1,transform:'translateY(0) scale(1)'}])}
$('#options-button').onclick=openOptions;
$('#apply-options').onclick=()=>{if(!$('#steps').checkValidity()||!$('#seed').checkValidity()||!$('#cfg').checkValidity())return toast('请检查步数和种子的取值范围');syncSizeLabel();$('#options').close();scheduleEstimate()};
function renderAttachments(){$('#attachments').replaceChildren();attachments.forEach((name,index)=>{const el=document.createElement('div');el.className='attachment';el.append(imageElement(name));const number=document.createElement('span');number.className='reference-number';number.setAttribute('translate','no');number.textContent='<image'+(index+1)+'>';el.append(number);const b=document.createElement('button');b.type='button';b.setAttribute('aria-label','移除参考图');b.append(icon('close'));b.onclick=()=>{attachments=attachments.filter(x=>x!==name);renderAttachments()};el.append(b);$('#attachments').append(el)});setMode();scheduleEstimate()}
async function addFiles(files){for(const file of files){if(attachments.length>=10){toast('最多添加 10 张参考图');break}if(!file.type.startsWith('image/'))continue;if(file.size>20*1024*1024){toast('图片应小于 20 MB');continue}const data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(file)});const result=await api('upload',{data});attachments.push(result.image);renderAttachments()}}
// Circular layout and staggered spring behavior ported from Ramotion/CircleMenu (MIT).
let creationOpen=false,creationVersion=0;
const creationItems=[['image','添加图片',()=>$('#file-input').click()],['template','任务模板',()=>openTemplates()],['sliders','图像参数',()=>openOptions()]];
creationItems.forEach(([symbol,label,action],index)=>{const b=document.createElement('button');b.className='circle-action';b.type='button';b.setAttribute('role','menuitem');b.setAttribute('aria-label',label);b.append(icon(symbol));const tip=document.createElement('span');tip.textContent=label;tip.className='circle-label';b.append(tip);const angle=index*Math.PI/6;b.dataset.x=Math.sin(angle)*118;b.dataset.y=-Math.cos(angle)*118;b.onclick=()=>{closeCreation();action()};$('#creation-menu').append(b)});
function closeCreation(){
 if(!creationOpen)return;creationOpen=false;const version=++creationVersion;$('#attach').setAttribute('aria-expanded','false');document.body.classList.remove('creation-open');
 const buttons=[...$('#creation-menu').children];const animations=buttons.map(b=>{b.getAnimations().forEach(a=>a.cancel());if(reduceMotion())return Promise.resolve();return b.animate([{transform:`translate(${b.dataset.x}px,${b.dataset.y}px) scale(1)`,opacity:1},{transform:'translate(0,0) scale(.3)',opacity:0}],{duration:200,easing:'ease-in',fill:'forwards'}).finished.catch(()=>{})});
 Promise.all(animations).then(()=>{if(version===creationVersion)$('#creation-menu').hidePopover()});
}
function openCreation(){
 if(creationOpen){closeCreation();return}creationVersion++;creationOpen=true;const menu=$('#creation-menu'),r=$('#attach').getBoundingClientRect();menu.style.left=Math.min(innerWidth-230,Math.max(10,r.left+r.width/2-22))+'px';menu.style.top=Math.max(12,r.top+r.height/2-22-140)+'px';menu.showPopover();$('#attach').setAttribute('aria-expanded','true');document.body.classList.add('creation-open');
 [...menu.children].forEach((b,i)=>{b.getAnimations().forEach(a=>a.cancel());const end=`translate(${b.dataset.x}px,${b.dataset.y}px) scale(1)`;b.style.transform=end;if(!reduceMotion())b.animate([{transform:'translate(0,0) scale(.2)',opacity:0},{transform:end,opacity:1}],{duration:500,delay:i*35,easing:'cubic-bezier(.16,1.2,.3,1)',fill:'backwards'})});menu.firstElementChild.focus({preventScroll:true});
}
$('#attach').onclick=openCreation;
document.addEventListener('pointerdown',e=>{if(!e.target.closest('#creation-menu,#attach'))closeCreation()});
window.addEventListener('resize',closeCreation);
$('#creation-menu').onkeydown=e=>{const buttons=[...$('#creation-menu').children];if(e.key==='Escape'){closeCreation();$('#attach').focus({preventScroll:true});e.preventDefault()}if(['ArrowRight','ArrowDown','ArrowLeft','ArrowUp','Home','End'].includes(e.key)){let i=buttons.indexOf(document.activeElement);i=e.key==='Home'?0:e.key==='End'?buttons.length-1:(i+(['ArrowRight','ArrowDown'].includes(e.key)?1:-1)+buttons.length)%buttons.length;buttons[i].focus({preventScroll:true});e.preventDefault()}};
$('#file-input').onchange=safe(async e=>{await addFiles(e.target.files);e.target.value=''});
$('#composer').ondragover=e=>{e.preventDefault();document.body.classList.add('drop-active')};$('#composer').ondragleave=()=>document.body.classList.remove('drop-active');$('#composer').ondrop=e=>{e.preventDefault();document.body.classList.remove('drop-active');const files=[...e.dataTransfer.files];safe(()=>addFiles(files))()};
$('#prompt').addEventListener('paste',e=>{const files=[...e.clipboardData.files];if(files.length&&!e.clipboardData.getData('text/plain').trim()){e.preventDefault();safe(()=>addFiles(files))()}});
$('#gallery-button').onclick=safe(async()=>{const images=await api('gallery');showPage('gallery');$('#gallery-grid').replaceChildren();for(const item of images){const el=document.createElement('div');el.className='gallery-item';el.append(imageElement(item.image),imageButtons(item.image));$('#gallery-grid').append(el)}if(!images.length){const p=document.createElement('p');p.className='gallery-empty';p.textContent='暂无图片';$('#gallery-grid').append(p)}});
$('#session-menu').onclick=()=>{$('#rename-input').value=session.title;$('#session-options').showModal()};$('#rename-session').onclick=safe(async()=>{await api('session/rename',{id:session.id,title:$('#rename-input').value});$('#session-options').close();await loadSession(session.id);await refreshSessions()});
$('#delete-session').onclick=()=>askDeleteSession(session);
// Deleting a chat removes its messages and job logs, and its images unless the switch is turned off.
let deletingSession=null;
function askDeleteSession(target){deletingSession=target;$('#delete-session-text').textContent=`将删除“${target.title}”中的所有消息。`;$('#delete-session-images').checked=true;$('#confirm-delete-session').disabled=false;$('#delete-session-dialog').showModal()}
$('#confirm-delete-session').onclick=safe(async()=>{const target=deletingSession;if(!target)return;$('#confirm-delete-session').disabled=true;try{const result=await api('session/delete',{id:target.id,delete_images:$('#delete-session-images').checked});$('#delete-session-dialog').close();$('#session-options').close();const gone=new Set(result.deleted_images);if(gone.size){attachments=attachments.filter(x=>!gone.has(x));renderAttachments()}const page=pageName;if(session?.id===target.id)reset();if(page!=='workspace')$('#'+page+'-button').click();await refreshSessions();toast(gone.size?`会话已删除，同时删除了 ${gone.size} 张图片`:'会话已删除')}finally{$('#confirm-delete-session').disabled=false}});
$('#reveal-data').onclick=safe(()=>api('reveal',{}));
// Model version and speed preset live next to the prompt, like the official demo's quick controls.
function warnTurboVariant(){if(variant==='uc'&&preset==='turbo')toast('极速 LoRA 基于官方权重训练，与无审查模型搭配时效果可能较差。')}
function syncSwitches(){$$('[data-variant]').forEach(b=>b.classList.toggle('active',b.dataset.variant===variant));$$('[data-preset]').forEach(b=>b.classList.toggle('active',b.dataset.preset===preset));const turbo=preset==='turbo';$('#negative-prompt').disabled=$('#cfg').disabled=turbo;if(turbo){$('#negative-prompt').value='';$('#cfg').value=1}}
$$('[data-variant]').forEach(b=>b.onclick=safe(async()=>{variant=b.dataset.variant;syncSwitches();scheduleEstimate();warnTurboVariant();await api('preferences',{transformer_variant:variant});await refreshStatus();const key=variant==='uc'?'transformer_uc':'transformer_official';if(!lastStatus?.components?.[key]?.ready)toast(t('请先在“模型设置”中下载：')+t(COMPONENT_TITLES[key]))}));
$$('[data-preset]').forEach(b=>b.onclick=safe(async()=>{preset=b.dataset.preset;$('#steps').value=PRESET_STEPS[preset];syncSwitches();scheduleEstimate();warnTurboVariant();await api('preferences',{preset})}));
$('#steps').addEventListener('input',()=>{const steps=Number($('#steps').value);const match=Object.entries(PRESET_STEPS).find(([name,value])=>value===steps&&(name!=='turbo'||preset==='turbo'));preset=match?match[0]:'custom';syncSwitches();scheduleEstimate()});
async function refreshStatus(){lastStatus=await api('status');renderComponents();const m=lastStatus.model;const ratio=m.total?m.bytes/m.total:0;const label=m.ready?'图像模型已就绪':m.verifying?'正在校验模型':m.downloading?`模型下载 ${Math.floor(ratio*100)}%`:'图像模型待下载';$('#model-status span:last-child').textContent=label;$('#model-status .status-dot').classList.toggle('amber',!m.ready);$('#model-path').textContent=m.path;$('#data-path').textContent=lastStatus.data;renderMemoryWarning();pendingJobs=lastStatus.pending||[];if(lastStatus.active?.state==='running'&&lastStatus.active.mode!=='enhance'&&!job){job=lastStatus.active;renderJob()}renderTaskTray();updateSend()}
// Jobs need 12–19 GB of unified memory; warn while idle when other apps leave too little.
function renderMemoryWarning(){const system=lastStatus?.system,box=$('#memory-warning');if(!system)return;const low=system.memory_available<10e9&&!lastStatus.active;box.hidden=!low;if(low)box.textContent=t(`可用内存仅 ${(system.memory_available/1e9).toFixed(1)} GB，建议先关闭占用内存的应用。`)}
document.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key==='n'){e.preventDefault();reset()}if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();$('#search').hidden=false;$('#search').focus()}});
const welcomeCopy={
 zh:['今天，想创作些什么？','把脑海里的画面，变成作品。','从一个想法，开始一幅画。','让灵感，在这里成形。','换个视角，试试新的可能。','下一幅作品，由你开启。'],
 en:['What will you create today?',"Let’s bring an idea to life.",'Your next image starts here.','Make a little room for imagination.','Give your ideas a new perspective.',"Let’s make something worth keeping."],
 ru:['Что создадим сегодня?','Превратим идею в картинку.','Следующее изображение начинается здесь.','Немного места для воображения.','Посмотрим на идею с новой стороны.','Сделаем то, что захочется сохранить.']
};
let welcomeLanguage=StudioI18n.choice,welcomeCycle=true,welcomeIndex=0,welcomeKey='',welcomeTimer=null,welcomeVersion=0;
$('#welcome-language').value=welcomeLanguage;$('#welcome-cycle').checked=welcomeCycle;
function welcomeLocale(){return StudioI18n.locale()}
function welcomeAvailable(){return pageName==='workspace'&&!session?.messages.length&&!document.hidden}
function stopWelcome(){clearTimeout(welcomeTimer);welcomeTimer=null;welcomeVersion++;$('#welcome-line').getAnimations({subtree:true}).forEach(a=>a.cancel())}
function scheduleWelcome(){clearTimeout(welcomeTimer);if(welcomeAvailable()&&welcomeCycle&&!reduceMotion()&&!$('#prompt').value.trim())welcomeTimer=setTimeout(rotateWelcome,24000)}
function paintWelcome(animate=true){
 const locale=welcomeLocale(),lines=welcomeCopy[locale]||welcomeCopy.en,text=lines[welcomeIndex%lines.length],line=$('#welcome-line');
 line.replaceChildren();line.lang=locale;line.setAttribute('aria-label',text);
 const units=locale==='zh'?[...text]:text.split(/(\s+)/);
 units.forEach((unit,i)=>{const span=document.createElement('span');span.textContent=unit;span.setAttribute('aria-hidden','true');span.className='welcome-unit';span.dataset.tone=['#bd507c','#9959be','#5c71c6','#367f9f','#428774','#91803c','#b16c39'][i%7];line.append(span);if(animate&&!reduceMotion())span.animate([{opacity:0,color:span.dataset.tone,filter:'blur(6px)',transform:'translateY(12px)',textShadow:'0 2px 12px '+span.dataset.tone},{offset:.28,opacity:1,color:span.dataset.tone,filter:'blur(0px)',transform:'translateY(0)',textShadow:'0 1px 7px '+span.dataset.tone+'44'},{offset:.62,opacity:1,color:span.dataset.tone,filter:'blur(0px)',transform:'translateY(0)',textShadow:'0 0 0 transparent'},{opacity:1,color:'#505050',filter:'blur(0px)',transform:'translateY(0)',textShadow:'0 0 0 transparent'}],{duration:2400,delay:i*Math.min(48,550/units.length),easing:'linear',fill:'backwards'})});
}
async function rotateWelcome(){
 if(!welcomeAvailable()||$('#prompt').value.trim())return;
 const version=++welcomeVersion,units=[...$('#welcome-line').children];
 await Promise.all(units.map((el,i)=>el.animate([{opacity:1,filter:'blur(0px)',transform:'translateY(0)'},{opacity:0,color:el.dataset.tone,filter:'blur(4px)',transform:'translateY(-7px)'}],{duration:220,delay:i*Math.min(12,150/units.length),easing:'ease-in',fill:'forwards'}).finished.catch(()=>{})));
 if(version!==welcomeVersion)return;
 welcomeIndex++;paintWelcome();scheduleWelcome();
}
function syncWelcome(reset=false){
 if(typeof welcomeLanguage==='undefined')return;
 const key=welcomeLocale();
 if(key!==welcomeKey||reset){stopWelcome();welcomeKey=key;welcomeIndex=0;paintWelcome(welcomeAvailable());}
 if(!welcomeAvailable()||$('#prompt').value.trim()){stopWelcome();return;}
 if(!welcomeTimer)scheduleWelcome();
}
$('#welcome-language').onchange=safe(async e=>{const choice=e.target.value;await api('preferences',{interface_language:choice});welcomeLanguage=choice;StudioI18n.setLanguage(choice);syncWelcome(true);scheduleEstimate()});
$('#welcome-cycle').onchange=safe(async e=>{welcomeCycle=e.target.checked;stopWelcome();paintWelcome(false);scheduleWelcome();await api('preferences',{welcome_cycle:welcomeCycle})});
document.addEventListener('visibilitychange',()=>syncWelcome());matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',()=>{stopWelcome();paintWelcome(false);scheduleWelcome()});
async function restorePreferences(){const p=await api('preferences');welcomeLanguage=p.interface_language;StudioI18n.setLanguage(welcomeLanguage);welcomeCycle=p.welcome_cycle;$('#welcome-language').value=welcomeLanguage;$('#welcome-cycle').checked=welcomeCycle;variant=p.transformer_variant;preset=p.preset;if(PRESET_STEPS[preset])$('#steps').value=PRESET_STEPS[preset];$('#thinking-budget').value=String(p.thinking_budget);syncSwitches();syncWelcome(true)}
document.addEventListener('DOMContentLoaded',()=>{Promise.all([restorePreferences(),refreshSessions(),refreshStatus()]).then(()=>scheduleEstimate()).catch(e=>toast('连接失败：'+e.message));setInterval(()=>refreshStatus().catch(()=>{}),2000);setInterval(()=>{pollJob();pollEnhance()},800);setMode();updateSend()},{once:true});
window.addEventListener('studio-language',()=>{if(typeof welcomeLanguage!=='undefined'){welcomeLanguage=StudioI18n.choice;syncWelcome(true)}});
