/* Image controls, model files, estimates and diagnostics. */
const COMPONENT_TITLES={base:'基础文件（配置与 VAE）',text_encoder:'文字编码器',transformer_official:'官方图像模型',transformer_uc:'无审查图像模型',turbo:'极速 LoRA',pe_t2i:'生图增强模型',pe_i2i:'改图增强模型'};
const COMPONENT_NOTES={base:'必需',text_encoder:'必需，Qwen3-VL-8B（8 位）',transformer_official:'官方权重（GGUF Q8_0）',transformer_uc:'社区修改版（GGUF Q8_0）',turbo:'“极速”模式需要',pe_t2i:'“增强提示词”生成图片时需要',pe_i2i:'“增强提示词”修改图片时需要'};
function currentSize(){return $('#size').value.split(',').map(Number)}
function enhanceOn(){return $('#enhance').checked}
function generationOptions(){
 const [width,height]=currentSize();
 return {width,height,enhance:enhanceOn(),ratio_mode:$('#ratio-mode').value,exact_text:$('#exact-text').value,negative_prompt:$('#negative-prompt').value,cfg:Number($('#cfg').value),count:Number($('#image-count').value),
  steps:Number($('#steps').value),seed:Number($('#seed').value),transparent:$('#transparent').checked,preset,variant,
  use_kv_cache:!$('#full-references').checked,previews:$('#previews').checked,thinking_budget:Number($('#thinking-budget').value)};
}
function requiredComponents(){
 const keys=['base','text_encoder',variant==='uc'?'transformer_uc':'transformer_official'];
 if(preset==='turbo')keys.push('turbo');
 if(enhanceOn())keys.push(attachments.length?'pe_i2i':'pe_t2i');
 return keys;
}
function missingComponents(){const components=lastStatus?.components;if(!components)return [];return requiredComponents().filter(key=>!components[key]?.ready)}
function formatBytes(value){const ru=StudioI18n.locale()==='ru';return value>=1e9?(value/1e9).toFixed(1)+(ru?' ГБ':' GB'):(value/1e6).toFixed(0)+(ru?' МБ':' MB')}
function renderComponents(){
 const list=$('#component-list'),components=lastStatus?.components||{};
 for(const [key,item] of Object.entries(components)){
  let row=list.querySelector('[data-component="'+key+'"]');
  if(!row){
   row=document.createElement('div');row.className='enhancer-row component-row';row.dataset.component=key;
   const heading=document.createElement('strong');heading.textContent=COMPONENT_TITLES[key]||key;
   const note=document.createElement('p');note.className='muted small component-note';note.textContent=COMPONENT_NOTES[key]||'';
   const detail=document.createElement('p');detail.className='muted small component-detail';
   const progress=document.createElement('progress');progress.max=1;
   const button=document.createElement('button');button.className='text-button';button.type='button';
   button.onclick=safe(async()=>{await api('model/download',{components:[key]});await refreshStatus()});
   row.append(heading,note,detail,progress,button);list.append(row);
  }
  row.querySelector('.component-detail').textContent=item.ready?`已就绪　${formatBytes(item.total)}`:`${formatBytes(item.bytes)} / ${formatBytes(item.total)}`;
  row.querySelector('progress').value=item.total?item.bytes/item.total:0;
  row.querySelector('progress').hidden=item.ready;
  const button=row.querySelector('button');button.disabled=item.ready||item.downloading||item.queued;
  button.textContent=item.ready?'已下载':item.downloading?'正在下载…':item.queued?'排队中':item.bytes?'继续下载':'下载';
 }
 const system=lastStatus?.system;if(system)$('#disk-info').textContent=`可用空间 ${formatBytes(system.free_disk)}`;
 const missing=Object.entries(components).filter(([,item])=>!item.ready);
 const running=Object.values(components).some(item=>item.downloading||item.queued);
 $('#download-all').disabled=!missing.length||running;
 $('#download-all').textContent=missing.length?`下载全部缺少的文件（${formatBytes(missing.reduce((sum,[,item])=>sum+item.total-item.bytes,0))}）`:'全部文件已就绪';
 const m=lastStatus?.model||{};
 $('#download-speed').textContent=running&&m.speed>0?`${(m.speed/1e6).toFixed(1)} MB/s`:running?'正在测量速度…':'';
 $('#download-eta').textContent=running&&m.eta?`预计剩余 ${m.eta>=3600?Math.floor(m.eta/3600)+' 小时 ':''}${Math.ceil((m.eta%3600)/60)} 分钟`:'';
 $('#download-error').hidden=!m.error;$('#download-error').textContent=m.error||'';
}
$('#download-all').onclick=safe(async()=>{const keys=Object.entries(lastStatus?.components||{}).filter(([,item])=>!item.ready).map(([key])=>key);if(keys.length)await api('model/download',{components:keys});await refreshStatus()});
function promptDetails(meta){
 const details=document.createElement('details');details.className='prompt-details';
 const summary=document.createElement('summary');summary.textContent='生成详情';details.append(summary);
 const settings=[meta.variant==='uc'?'无审查':'官方',meta.turbo?'极速':null,meta.dtype,meta.reference_resolution&&meta.reference_images?.length?`参考图 ${meta.reference_resolution} px`:null,meta.step_seconds?`每步 ${meta.step_seconds} 秒`:null].filter(Boolean).map(value=>t(value)).join(' · ');
 for(const [label,value] of [['原始提示词',meta.original_prompt],['增强提示词',meta.enhanced_prompt],['实际提示词',meta.effective_prompt],['随机种子',(meta.seeds||[meta.seed]).join(', ')],['设置',settings]]){
  if(value===undefined||value===null||value==='')continue;
  const heading=document.createElement('p');heading.className='muted small';heading.textContent=label;
  const body=document.createElement('p');body.className='prompt-value';body.setAttribute('translate','no');body.textContent=String(value);details.append(heading,body);
 }
 return details;
}
function syncSizeLabel(){const [width,height]=currentSize();$('#options-label').textContent=`${width} × ${height}`;$('#size-warning').hidden=width*height<=1600*1600}
function formatDuration(seconds){return seconds>=90?`约 ${Math.round(seconds/60)} 分钟`:`约 ${Math.max(1,Math.round(seconds))} 秒`}
let estimateTimer=null,estimateVersion=0;
function scheduleEstimate(){clearTimeout(estimateTimer);estimateTimer=setTimeout(()=>refreshEstimate().catch(()=>{}),350)}
async function refreshEstimate(){
 const version=++estimateVersion;
 const result=await api('estimate',{images:attachments,...generationOptions()});
 if(version!==estimateVersion)return;
 $('#eta').textContent=t(formatDuration(result.seconds));
 $('#eta').title=t(`每步约 ${result.step_seconds} 秒`);
 const plan=$('#reference-plan');
 if(attachments.length&&(result.reference_resolution<1024||attachments.length>2)){plan.hidden=false;plan.textContent=t(`${attachments.length} 张参考图 → 按 ${result.reference_resolution} 像素编码，缓存约 ${result.kv_cache_gb} GB`)}
 else plan.hidden=true;
}
$('#size').addEventListener('change',()=>{$('#ratio-mode').value=$('#ratio-mode').value==='auto'&&enhanceOn()?'auto':'fixed';syncSizeLabel();scheduleEstimate()});
function syncEnhance(value){$('#enhance').checked=$('#enhance-quick').checked=value;if(!value&&$('#ratio-mode').value==='auto')$('#ratio-mode').value='fixed';scheduleEstimate()}
$('#enhance').addEventListener('change',()=>syncEnhance($('#enhance').checked));
$('#enhance-quick').addEventListener('change',()=>syncEnhance($('#enhance-quick').checked));
$('#negative-prompt').addEventListener('input',()=>{if(!$('#negative-prompt').value.trim())$('#cfg').value=1;else if(Number($('#cfg').value)<=1)$('#cfg').value=2;scheduleEstimate()});
for(const id of ['#cfg','#image-count','#full-references','#transparent'])$(id).addEventListener('change',scheduleEstimate);
$('#text-preset').onclick=()=>{preset='quality';$('#steps').value=40;syncSwitches();$('#ratio-mode').value='auto';syncEnhance(true);syncSizeLabel();$('#exact-text').focus();toast('已选择精细模式和提示词增强，请填写图中文字')};
async function runDiagnostics(){
 const box=$('#diagnostics');box.replaceChildren();const waiting=document.createElement('p');waiting.className='muted small';waiting.textContent='正在检测…';box.append(waiting);
 $('#environment-check').disabled=true;
 try{
  const items=await api('diagnostics',{});box.replaceChildren();
  for(const item of items.filter(item=>item.state!=='checking')){
   const row=document.createElement('div');row.className='diagnostic-row '+item.state;
   const title=document.createElement('span');title.textContent=item.title;
   const detail=document.createElement('span');detail.className='muted small';detail.textContent=item.state==='pass'?item.detail:(item.diagnostic||item.detail);
   const mark=document.createElement('span');mark.className='diagnostic-state';mark.textContent=item.state==='pass'?'通过':item.state==='optional'?'可选':'需要处理';
   row.append(mark,title,detail);box.append(row);
  }
 }finally{$('#environment-check').disabled=false}
}
function openDiagnostics(){showPage('settings');runDiagnostics().catch(e=>toast(e.message))}
$('#environment-check').onclick=safe(runDiagnostics);
