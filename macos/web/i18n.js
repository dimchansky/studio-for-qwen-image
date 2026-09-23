/* Translate application-owned text only. Conversation text, titles and filenames
   are explicitly excluded, including during live language changes. */
(() => {
 // Chinese is the source language; every other locale has its own catalog and patterns.
 const catalogs=window.STUDIO_MESSAGES||{},compiled={};
 for(const [code,list] of Object.entries(window.STUDIO_PATTERNS||{}))compiled[code]=list.map(([a,b])=>[new RegExp(a,'s'),b]);
 const LOCALES=['zh','en','ru'];
 let choice=document.querySelector('meta[name=studio-language]')?.content||window.STUDIO_LANGUAGE||'auto';
 const valid=v=>v==='auto'||LOCALES.includes(v)?v:'auto';choice=valid(choice);
 const systemLocale=()=>{const l=navigator.language.toLowerCase();return l.startsWith('zh')?'zh':l.startsWith('ru')?'ru':'en'};
 const locale=()=>choice==='auto'?systemLocale():choice;
 function t(value,context){
  const code=locale();if(typeof value!=='string'||code==='zh')return value;
  // A missing translation falls back to English rather than showing the Chinese source.
  const text=value.trim();
  for(const fallback of code==='en'?['en']:[code,'en']){
   const messages=catalogs[fallback]||{};
   if(context&&Object.hasOwn(messages,context+':'+text))return value.replace(text,messages[context+':'+text]);if(Object.hasOwn(messages,text))return value.replace(text,messages[text]);
   for(const [pattern,replacement] of compiled[fallback]||[])if(pattern.test(value))return value.replace(pattern,replacement);
  }
  return value;
 }
 const original=new WeakMap(),attributes=new WeakMap();
 const excluded=e=>e?.closest('[translate="no"], [data-user-content], script, style, code, pre, #welcome-line');
 function translateNode(node){
  if(node.nodeType===Node.TEXT_NODE){
   if(excluded(node.parentElement)||!node.nodeValue?.trim())return;
   const previous=original.get(node),source=previous&&node.nodeValue===previous.output?previous.source:node.nodeValue;
   const output=t(source,node.parentElement?.closest('[data-i18n-context]')?.dataset.i18nContext);original.set(node,{source,output});if(node.nodeValue!==output)node.nodeValue=output;
  }else if(node.nodeType===Node.ELEMENT_NODE){
   if(excluded(node))return;
   const saved=attributes.get(node)||{};
   for(const name of ['title','aria-label','placeholder','alt','label'])if(node.hasAttribute(name)){
    const current=node.getAttribute(name),old=saved[name],source=old&&old.output===current?old.source:current,output=t(source);
    saved[name]={source,output};if(current!==output)node.setAttribute(name,output);
   }
   attributes.set(node,saved);node.childNodes.forEach(translateNode);
  }
 }
 let observer;
 function render(root=document.body){observer?.disconnect();translateNode(root);observe();}
 function observe(){if(observer&&document.body)observer.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['title','aria-label','placeholder','alt','label','translate','data-user-content']});}
 function setLanguage(value){choice=valid(value);document.documentElement.lang={zh:'zh-CN',en:'en',ru:'ru'}[locale()];render();window.dispatchEvent(new CustomEvent('studio-language',{detail:choice}));}
 window.StudioI18n={t,locale,get choice(){return choice},setLanguage,render};window.t=t;
 function start(){observer=new MutationObserver(records=>{observer.disconnect();for(const record of records){if(record.type==='childList')record.addedNodes.forEach(translateNode);else translateNode(record.target)}observe()});setLanguage(choice);}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
