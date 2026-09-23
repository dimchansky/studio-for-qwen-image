/* Task templates for the capabilities described in the Qwen-Image-2.1 README, blog and
   official demo cases. Prompts are model-facing: Chinese for a Chinese interface, English
   otherwise. Text in parentheses is a placeholder for the user to replace. */
const TEMPLATES=[
 {id:'rgba',title:'透明素材',note:'生成带透明背景的 PNG（贴纸、图标、角色立绘）。',images:0,options:{transparent:true},
  zh:'（描述主体），完整呈现主体，边缘干净清晰，没有背景。',
  en:'(describe the subject), shown in full with clean, crisp edges and no background.'},
 {id:'remove-bg',title:'移除背景',note:'把照片中的主体抠出为透明 PNG。',images:1,
  zh:'Remove the background, and output a PNG image',
  en:'Remove the background, and output a PNG image'},
 {id:'extract',title:'提取主体',note:'只保留指定物体，输出透明 PNG。',images:1,options:{transparent:true},
  zh:'从 <image1> 中提取（物体名称），保持其形状、材质和细节完全不变，背景透明。',
  en:'Extract the (object) from <image1>, keeping its shape, materials and details exactly unchanged, on a transparent background.'},
 {id:'background',title:'更换背景',note:'保留人物或商品，替换场景。',images:1,
  zh:'保持 <image1> 中的主体完全不变，将背景替换为（新的场景），光线方向与阴影自然统一。',
  en:'Keep the subject of <image1> exactly unchanged and replace the background with (new scene), with consistent lighting direction and natural shadows.'},
 {id:'product',title:'商品场景图',note:'商品外观、文字和材质保持一致。',images:1,
  zh:'保持 <image1> 中商品的全部外观完全不变，包括形状、标识、文字与材质，将其放置在（场景描述）中，真实自然的光影与接触阴影。',
  en:'Keep every detail of the product in <image1> exactly unchanged — shape, logo, printed text and materials — and place it in (scene description) with realistic lighting and contact shadows.'},
 {id:'text',title:'替换或翻译文字',note:'文字请写在引号里。',images:1,
  zh:'将 <image1> 中的文字“（原文字）”替换为“（新文字）”，保持原有字体风格、颜色、透视和光照，其他内容保持不变。',
  en:'Replace the text "(old text)" in <image1> with "(new text)", matching the original font style, color, perspective and lighting. Keep everything else unchanged.'},
 {id:'style',title:'风格化',note:'整体转换画风，保留构图。',images:1,
  zh:'将 <image1> 整体转换为（水彩画 / 油画 / 动漫 等）风格，保持原有构图、比例、视角和主体位置不变，整幅画面都呈现该画材的质感。',
  en:'Transform <image1> into (watercolor / oil painting / anime …) style across the entire image. Preserve the original composition, aspect ratio, viewpoint and subject placement, and make the whole surface read as that medium.'},
 {id:'style-ref',title:'参考风格',note:'按第二张图的风格重绘第一张图。',images:2,
  zh:'以 <image2> 的视觉风格（配色、笔触、光影）重绘 <image1>，保持 <image1> 的内容和构图不变。',
  en:'Redraw <image1> in the visual style of <image2> (palette, brushwork, lighting), keeping the content and composition of <image1> unchanged.'},
 {id:'tryon',title:'虚拟试穿',note:'第一张为人物，其余为服饰。',images:2,
  zh:'让 <image1> 中的人物穿上 <image2> 中的（服装），保持人物的面容、姿势和背景不变，服装的版型、颜色和细节与 <image2> 一致。',
  en:'Dress the person in <image1> in the (garment) from <image2>, keeping the person\'s face, pose and background unchanged; match the cut, color and details of <image2>.'},
 {id:'face',title:'替换人脸',note:'第二张图提供面部身份。',images:2,
  zh:'将 <image1> 中人物的脸替换为 <image2> 中人物的脸，匹配肤色、光照和角度，保持 <image1> 的发型、身体和背景不变。',
  en:'Replace the face of the person in <image1> with the face of the person in <image2>, matching skin tone, lighting and head angle; keep the hair, body and background of <image1>.'},
 {id:'group',title:'多人合照',note:'每张图一位人物（最多 10 张）。',images:2,
  zh:'以 <image1>、<image2> 中的人物为身份参考，生成一张他们在（场景）中的全新合照，保持每个人的面容特征，姿态自然。',
  en:'Using the people in <image1> and <image2> as identity references, generate a brand-new group photo of them together in (scene), preserving each person\'s facial identity, with natural poses.'},
 {id:'expression',title:'表情与姿势',note:'局部修改人物表情或动作。',images:1,
  zh:'将 <image1> 中人物的表情改为（开怀大笑），动作调整为（比耶），保持身份、服装、取景和背景不变。',
  en:'Change the expression of the person in <image1> to (a big laugh) and the pose to (a peace sign), keeping identity, clothing, framing and background unchanged.'},
 {id:'restore',title:'老照片修复上色',note:'去除划痕、提高清晰度并自然上色。',images:1,
  zh:'显著提升这张老照片的分辨率与清晰度，修复为真实自然的彩色高保真照片。去除灰尘、划痕、斑点、褪色和过多颗粒；恢复细节，明暗均衡，不过度锐化。严格保持原有构图、人物身份、姿势、表情和光线方向，使用符合年代和材质的克制色彩。',
  en:'Significantly improve the resolution and overall clarity of this vintage photograph and restore it as a realistic, naturally colorized high-fidelity photograph. Remove age-related dust, scratches, spots, fading, and excessive grain; recover fine detail and balanced highlights and shadows without oversharpening. Strictly preserve the original framing, identities, poses, expressions and lighting direction. Use believable, restrained colors appropriate to the period and materials.'},
 {id:'outpaint',title:'扩图',note:'向四周延展画面（使用更宽的画布）。',images:1,options:{size:'1376,768',ratio:'fixed'},
  zh:'将 <image1> 的画面向左右两侧自然延展到更宽的画布，延续原有场景、光线和透视，原有内容保持不变。',
  en:'Extend <image1> naturally beyond its left and right borders to fill a wider canvas, continuing the scene, lighting and perspective; keep the original content unchanged.'},
 {id:'panorama',title:'360° 全景图',note:'由一张照片生成 2:1 等距柱状全景。',images:1,options:{size:'1536,768',ratio:'fixed'},
  zh:'由输入的透视图生成完整的 360 度等距柱状投影全景图，覆盖水平 360 度与垂直 180 度视野，左右边缘无缝衔接，场景连续一致，画面比例严格为 2:1。',
  en:'Generate a complete 360-degree equirectangular panorama from the input perspective image. Use a true equirectangular projection covering the entire 360-degree horizontal and 180-degree vertical field of view, with seamless left and right edges and a single continuous scene, at an exact 2:1 aspect ratio.'},
 {id:'turnaround',title:'角色三视图',note:'正面、侧面、背面设定图。',images:1,
  zh:'为 <image1> 中的角色生成三视图设定图：正面、侧面、背面并排站立，设计完全一致，纯色背景，比例统一。',
  en:'Create a character turnaround sheet of the character in <image1>: front, side and back views standing side by side, with a perfectly consistent design, plain background and matching proportions.'},
 {id:'infographic',title:'信息图 / 海报',note:'文字较多时建议开启提示词增强和精细模式。',images:0,options:{enhance:true,preset:'quality'},
  zh:'一张关于（主题）的信息图海报，标题为“（标题）”，分为（3）个板块，配有图标和简洁的说明文字，版式清晰，配色（风格）。',
  en:'An infographic poster about (topic) titled "(title)", organised into (3) sections with icons and short captions, a clear layout and a (style) color palette.'},
];
function applyTemplate(template){
 const words=StudioI18n.locale()==='zh'?template.zh:template.en,options=template.options||{};
 $('#transparent').checked=!!options.transparent;
 if(options.size){$('#size').value=options.size;syncSizeLabel()}
 if(options.ratio)$('#ratio-mode').value=options.ratio;
 if(options.enhance)syncEnhance(true);
 if(options.preset){preset=options.preset;$('#steps').value=PRESET_STEPS[preset];syncSwitches()}
 $('#prompt').value=words;$('#templates-dialog').close();showPage('workspace');$('#prompt').focus();updateSend();scheduleEstimate();
 if(attachments.length<template.images)toast(t(`这个模板需要至少 ${template.images} 张参考图，请添加图片。`));
}
function openTemplates(){
 const list=$('#template-list');list.replaceChildren(...TEMPLATES.map(template=>{
  const b=document.createElement('button');b.type='button';b.className='template-card';
  const title=document.createElement('strong');title.textContent=template.title;
  const note=document.createElement('span');note.className='muted small';note.textContent=template.note;
  const need=document.createElement('span');need.className='template-images';need.textContent=template.images?`参考图 ≥ ${template.images}`:'文生图';
  b.append(title,note,need);b.onclick=()=>applyTemplate(template);return b;
 }));
 $('#templates-dialog').showModal();
}
