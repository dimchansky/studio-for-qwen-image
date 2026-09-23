const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const web=path.join(__dirname,'../macos/web');
// Small DOM fixture exercises real translator ownership and reversible updates.
class Element {
 constructor(attrs={},children=[]){this.nodeType=1;this.attrs={...attrs};this.childNodes=children;this.dataset={};if(attrs['data-i18n-context'])this.dataset.i18nContext=attrs['data-i18n-context'];children.forEach(n=>n.parentElement=this);}
 hasAttribute(k){return k in this.attrs}getAttribute(k){return this.attrs[k]??null}setAttribute(k,v){this.attrs[k]=v}
 closest(selector){for(let e=this;e;e=e.parentElement){if(selector.includes('[data-i18n-context]')&&e.attrs['data-i18n-context'])return e;if(selector.includes('[translate="no"]')&&(e.attrs.translate==='no'||e.attrs['data-user-content']))return e;}return null;}
}
const text=value=>({nodeType:3,nodeValue:value});
const ui=text('模型设置'),user=text('模型设置'),title=text('新会话'),dynamic=text('正在生成 3/40'),preset=text('标准'),fallback=text('输入消息…');
const input=new Element({'placeholder':'描述画面，或添加图片…','aria-label':'消息内容'});
const body=new Element({},[new Element({},[ui]),new Element({translate:'no'},[user]),new Element({translate:'no'},[title]),new Element({},[dynamic]),new Element({'data-i18n-context':'preset'},[preset]),new Element({},[fallback]),input]);
const ctx={window:{dispatchEvent(){}},document:{body,readyState:'complete',documentElement:{},querySelector(){return null}},navigator:{language:'en-US'},Node:{TEXT_NODE:3,ELEMENT_NODE:1},MutationObserver:class{disconnect(){}observe(){}},CustomEvent:class{}};
vm.createContext(ctx);for(const f of ['locale-data.js','i18n.js'])vm.runInContext(fs.readFileSync(path.join(web,f),'utf8'),ctx);
const {StudioI18n,t}=ctx.window;
assert.equal(ui.nodeValue,'Settings');assert.equal(dynamic.nodeValue,'Generating 3/40');assert.equal(preset.nodeValue,'Standard');
assert.equal(input.getAttribute('placeholder'),'Describe an image, or add a reference…');
for(const [node,value] of [[user,'模型设置'],[title,'新会话']])assert.equal(node.nodeValue,value);
StudioI18n.setLanguage('ru');
assert.equal(ui.nodeValue,'Настройки');assert.equal(dynamic.nodeValue,'Генерация 3/40');assert.equal(preset.nodeValue,'Стандарт');
// A string without a Russian entry falls back to English, never to the Chinese source.
assert.equal(fallback.nodeValue,'Send a message…');
assert.equal(t('约 4 分钟'),'≈ 4 мин');assert.equal(t('3 张参考图 → 按 896 像素编码，缓存约 5.89 GB'),'Референсов: 3 → кодируются по 896 px, кэш ≈ 5.89 ГБ');
assert.equal(t('1184 × 896（4:3）'),'1184 × 896 (4:3)');
StudioI18n.setLanguage('zh');assert.equal(ui.nodeValue,'模型设置');assert.equal(dynamic.nodeValue,'正在生成 3/40');assert.equal(preset.nodeValue,'标准');
StudioI18n.setLanguage('en');assert.equal(t('预计剩余 12 分钟'),'About 12 min remaining');assert.equal(t('预计剩余 2 小时 3 分钟'),'About 2 h 3 min remaining');assert.equal(t('768 × 768　40 步　186 秒'),'768 × 768　40 steps　186 s');
// A later status update must replace the saved source, not restore stale text.
dynamic.nodeValue='正在生成 4/40';StudioI18n.render();assert.equal(dynamic.nodeValue,'Generating 4/40');StudioI18n.setLanguage('zh');assert.equal(dynamic.nodeValue,'正在生成 4/40');
for(const code of ['en','ru']){
 assert.deepEqual(JSON.parse(JSON.stringify(ctx.window.STUDIO_MESSAGES[code])),JSON.parse(fs.readFileSync(path.join(web,'locales',code+'.json'),'utf8')));
 assert.deepEqual(JSON.parse(JSON.stringify(ctx.window.STUDIO_PATTERNS[code])),JSON.parse(fs.readFileSync(path.join(web,'locales','patterns-'+code+'.json'),'utf8')));
}
console.log('PASS: en/ru switching, English fallback, dynamic text, catalog sync and user text preservation');
