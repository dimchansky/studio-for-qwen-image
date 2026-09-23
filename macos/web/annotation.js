/* Circle, box and paint annotations, plus separate masks, as official I2I reference inputs.
   Prompt hints follow the official demo cases (examples/cases.json): colored marks name the
   region and must not be rendered; a separate white-on-black mask is the last reference. */
let annotationImage=null,annotationName='',annotationStrokes=[],annotationStroke=null;
const annotationCanvas=$('#annotation-canvas'),annotationContext=annotationCanvas.getContext('2d');
const ANNOTATION_COLORS={red:'#f23d3d',green:'#1fb84a',blue:'#2f6bff',yellow:'#ffd21f',white:'#ffffff'};
// The model reads these words: Chinese for a Chinese interface, English otherwise.
const HINTS={
 zh:{colors:{red:'红色',green:'绿色',blue:'蓝色',yellow:'黄色',white:'白色'},shapes:{circle:'圈选',box:'框选',brush:'涂抹'},
  region:(image,color,shape)=>`将 <image${image}> 中${color}${shape}区域内的内容修改为：（描述修改内容）；`,
  paint:image=>`在 <image${image}> 中白色涂抹标注的区域添加或修改：（描述内容）。`,
  marks:colors=>`${colors}标注线不得渲染在图像中。`,join:'、',
  mask:(mask,source)=>`<image${mask}> 是 <image${source}> 的蒙版：只修改白色区域，将其改为：（描述修改内容），其余部分保持不变。`},
 en:{colors:{red:'red',green:'green',blue:'blue',yellow:'yellow',white:'white'},shapes:{circle:'circle',box:'box',brush:'painted area'},
  region:(image,color,shape)=>`In <image${image}>, change the content inside the ${color} ${shape} to: (describe the change).`,
  paint:image=>`In the white painted region of <image${image}>, add or change: (describe the content).`,
  marks:colors=>`The ${colors} annotation marks must not appear in the final image.`,join:', ',
  mask:(mask,source)=>`<image${mask}> is a mask for <image${source}>: change only the white area to: (describe the change). Keep everything else unchanged.`}
};
function hintLanguage(){return StudioI18n.locale()==='zh'?HINTS.zh:HINTS.en}
function strokeWidth(stroke){const scale=Math.max(annotationCanvas.width,annotationCanvas.height);return stroke.tool==='brush'?Math.max(8,scale*.007*stroke.width):Math.max(2,scale*.0016*stroke.width)}
function drawAnnotation(mask=false){
 const ctx=annotationContext,w=annotationCanvas.width,h=annotationCanvas.height;ctx.clearRect(0,0,w,h);
 if(mask){ctx.fillStyle='#000';ctx.fillRect(0,0,w,h)}else ctx.drawImage(annotationImage,0,0,w,h);
 ctx.lineCap='round';ctx.lineJoin='round';
 for(const stroke of [...annotationStrokes,...(annotationStroke?[annotationStroke]:[])]){
  const points=stroke.points,color=mask?'#fff':ANNOTATION_COLORS[stroke.color];ctx.strokeStyle=ctx.fillStyle=color;ctx.lineWidth=strokeWidth(stroke);ctx.beginPath();
  const [a,b]=[points[0],points.at(-1)];
  if(stroke.tool==='circle'){ctx.ellipse((a.x+b.x)/2,(a.y+b.y)/2,Math.max(1,Math.abs(a.x-b.x)/2),Math.max(1,Math.abs(a.y-b.y)/2),0,0,2*Math.PI);if(mask)ctx.fill();else ctx.stroke()}
  else if(stroke.tool==='box'){ctx.rect(Math.min(a.x,b.x),Math.min(a.y,b.y),Math.abs(a.x-b.x),Math.abs(a.y-b.y));if(mask)ctx.fill();else ctx.stroke()}
  else{ctx.moveTo(a.x,a.y);if(points.length===1)ctx.lineTo(a.x+.1,a.y);for(const p of points.slice(1))ctx.lineTo(p.x,p.y);ctx.stroke()}
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
annotationCanvas.onpointerdown=event=>{if(event.button!==0)return;event.preventDefault();annotationCanvas.setPointerCapture(event.pointerId);annotationStroke={tool:$('#annotation-tool').value,color:$('#annotation-color').value,width:Number($('#annotation-width').value),points:[annotationPoint(event)]};drawAnnotation()};
annotationCanvas.onpointermove=event=>{if(annotationStroke){annotationStroke.points.push(annotationPoint(event));drawAnnotation()}};
annotationCanvas.onpointerup=event=>{if(annotationStroke){annotationStroke.points.push(annotationPoint(event));annotationStrokes.push(annotationStroke);annotationStroke=null;drawAnnotation()}};
annotationCanvas.onpointercancel=()=>{annotationStroke=null;drawAnnotation()};
$('#annotation-tool').onchange=()=>{if($('#annotation-tool').value==='brush'&&$('#annotation-color').value==='red'&&!annotationStrokes.length)$('#annotation-color').value='white'};
$('#annotation-undo').onclick=()=>{annotationStrokes.pop();drawAnnotation()};$('#annotation-clear').onclick=()=>{annotationStrokes=[];drawAnnotation()};
function markHint(image){
 const words=hintLanguage(),lines=[],colors=[];
 const groups=new Map();for(const stroke of annotationStrokes){const key=stroke.color+'|'+stroke.tool;if(!groups.has(key))groups.set(key,stroke)}
 for(const stroke of groups.values()){
  if(stroke.color==='white'&&stroke.tool==='brush'){lines.push(words.paint(image));continue}
  lines.push(words.region(image,words.colors[stroke.color],words.shapes[stroke.tool]));
  if(!colors.includes(words.colors[stroke.color]))colors.push(words.colors[stroke.color]);
 }
 if(colors.length)lines.push(words.marks(colors.join(words.join)));
 return lines.join('\n');
}
async function addAnnotation(mask){
 const originalIndex=attachments.indexOf(annotationName);
 const needOriginal=mask&&originalIndex<0;
 const added=mask?1+Number(needOriginal):Number(originalIndex<0);
 if(attachments.length+added>10)return toast('最多添加 10 张参考图');
 $('#annotation-apply').disabled=$('#annotation-mask').disabled=true;
 try{
  drawAnnotation(mask);const data=annotationCanvas.toDataURL('image/png').split(',')[1];drawAnnotation();
  const result=await api('upload',{data});
  let hint;
  if(mask){
   if(needOriginal)attachments.push(annotationName);
   // The mask goes last: the output takes the size of the last reference, which matches the original.
   attachments.push(result.image);
   hint=hintLanguage().mask(attachments.length,attachments.indexOf(annotationName)+1);
  }else{
   // The annotated copy stands in for the original, as in the official single-image case.
   if(originalIndex>=0)attachments[originalIndex]=result.image;else attachments.push(result.image);
   hint=markHint(attachments.indexOf(result.image)+1);
  }
  renderAttachments();showPage('workspace');$('#annotation-dialog').close();
  $('#prompt').value=($('#prompt').value.trim()+'\n'+hint).trim();$('#prompt').focus();updateSend();
 }finally{drawAnnotation()}
}
$('#annotation-apply').onclick=safe(()=>addAnnotation(false));$('#annotation-mask').onclick=safe(()=>addAnnotation(true));
