/* Circle/paint annotations and separate mask images use the official I2I reference input. */
let annotationImage=null,annotationName='',annotationStrokes=[],annotationStroke=null;
const annotationCanvas=$('#annotation-canvas'),annotationContext=annotationCanvas.getContext('2d');
function drawAnnotation(mask=false){
 const ctx=annotationContext,w=annotationCanvas.width,h=annotationCanvas.height;ctx.clearRect(0,0,w,h);
 if(mask){ctx.fillStyle='#000';ctx.fillRect(0,0,w,h)}else ctx.drawImage(annotationImage,0,0,w,h);
 ctx.strokeStyle=mask?'#fff':'#f23d3d';ctx.fillStyle=mask?'#fff':'#f23d3d';ctx.lineCap='round';ctx.lineJoin='round';
 for(const stroke of [...annotationStrokes,...(annotationStroke?[annotationStroke]:[])]){
  const points=stroke.points;ctx.beginPath();
  if(stroke.tool==='circle'){
   const [a,b]=[points[0],points.at(-1)];ctx.lineWidth=Math.max(4,w*.004);
   ctx.ellipse((a.x+b.x)/2,(a.y+b.y)/2,Math.max(1,Math.abs(a.x-b.x)/2),Math.max(1,Math.abs(a.y-b.y)/2),0,0,2*Math.PI);
   if(mask)ctx.fill();else ctx.stroke();
  }else{ctx.lineWidth=Math.max(14,w*.035);ctx.moveTo(points[0].x,points[0].y);if(points.length===1)ctx.lineTo(points[0].x+.1,points[0].y);for(const p of points.slice(1))ctx.lineTo(p.x,p.y);ctx.stroke()}
 }
 $('#annotation-undo').disabled=$('#annotation-clear').disabled=!annotationStrokes.length;
 $('#annotation-mask').disabled=$('#annotation-apply').disabled=!annotationStrokes.length;
}
function annotationPoint(event){const r=annotationCanvas.getBoundingClientRect();return {x:Math.max(0,Math.min(annotationCanvas.width,(event.clientX-r.left)*annotationCanvas.width/r.width)),y:Math.max(0,Math.min(annotationCanvas.height,(event.clientY-r.top)*annotationCanvas.height/r.height))}}
$('#viewer-annotate').onclick=safe(async()=>{
 annotationName=viewingImage;const image=new Image();image.src='/media/'+encodeURIComponent(annotationName);await image.decode();annotationImage=image;
 annotationCanvas.width=image.naturalWidth;annotationCanvas.height=image.naturalHeight;annotationStrokes=[];annotationStroke=null;drawAnnotation();
 $('#image-viewer').close();$('#annotation-dialog').showModal();
});
annotationCanvas.onpointerdown=event=>{if(event.button!==0)return;event.preventDefault();annotationCanvas.setPointerCapture(event.pointerId);annotationStroke={tool:$('#annotation-tool').value,points:[annotationPoint(event)]};drawAnnotation()};
annotationCanvas.onpointermove=event=>{if(annotationStroke){annotationStroke.points.push(annotationPoint(event));drawAnnotation()}};
annotationCanvas.onpointerup=event=>{if(annotationStroke){annotationStroke.points.push(annotationPoint(event));annotationStrokes.push(annotationStroke);annotationStroke=null;drawAnnotation()}};
annotationCanvas.onpointercancel=()=>{annotationStroke=null;drawAnnotation()};
$('#annotation-undo').onclick=()=>{annotationStrokes.pop();drawAnnotation()};$('#annotation-clear').onclick=()=>{annotationStrokes=[];drawAnnotation()};
async function addAnnotation(mask){
 const needOriginal=mask&&!attachments.includes(annotationName);
 if(attachments.length+1+Number(needOriginal)>10)return toast('最多添加 10 张参考图');
 $('#annotation-apply').disabled=$('#annotation-mask').disabled=true;
 try{
  drawAnnotation(mask);const data=annotationCanvas.toDataURL('image/png').split(',')[1];drawAnnotation();
  const result=await api('upload',{data});
  if(needOriginal)attachments.push(annotationName);attachments.push(result.image);setMode('image');renderAttachments();showPage('workspace');$('#annotation-dialog').close();
  const index=attachments.length;
  const hint=mask?t('使用 <image{mask}> 作为 <image{source}> 的蒙版，修改白色区域，保留其他部分。').replace('{mask}',String(index)).replace('{source}',String(attachments.indexOf(annotationName)+1)):t('修改 <image{image}> 中红色标注的区域，最终图片不要保留标记。').replace('{image}',String(index));
  $('#prompt').value=($('#prompt').value.trim()+'\n'+hint).trim();$('#prompt').focus();updateSend();
 }finally{drawAnnotation()}
}
$('#annotation-apply').onclick=safe(()=>addAnnotation(false));$('#annotation-mask').onclick=safe(()=>addAnnotation(true));
