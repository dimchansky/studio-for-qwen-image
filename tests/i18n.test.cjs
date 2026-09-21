const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const web=path.join(__dirname,'../macos/web');
// Small DOM fixture exercises real translator ownership and reversible updates.
class Element {
 constructor(attrs={},children=[]){this.nodeType=1;this.attrs={...attrs};this.childNodes=children;this.dataset={};if(attrs['data-i18n-context'])this.dataset.i18nContext=attrs['data-i18n-context'];children.forEach(n=>n.parentElement=this);}
 hasAttribute(k){return k in this.attrs}getAttribute(k){return this.attrs[k]??null}setAttribute(k,v){this.attrs[k]=v}
 closest(selector){for(let e=this;e;e=e.parentElement){if(selector.includes('[data-i18n-context]')&&e.attrs['data-i18n-context'])return e;if(selector.includes('[translate="no"]')&&(e.attrs.translate==='no'||e.attrs['data-user-content']))return e;}return null;}
}
const text=value=>({nodeType:3,nodeValue:value});
const ui=text('模型设置'),user=text('模型设置'),title=text('新会话'),stream=text('正在思考'),dynamic=text('正在生成 3/40'),effort=text('关闭');
const input=new Element({'placeholder':'输入消息…','aria-label':'消息内容'});
const body=new Element({},[new Element({},[ui]),new Element({translate:'no'},[user]),new Element({translate:'no'},[title]),new Element({translate:'no'},[stream]),new Element({},[dynamic]),new Element({'data-i18n-context':'thinking'},[effort]),input]);
const ctx={window:{dispatchEvent(){}},document:{body,readyState:'complete',documentElement:{},querySelector(){return null}},navigator:{language:'en-US'},Node:{TEXT_NODE:3,ELEMENT_NODE:1},MutationObserver:class{disconnect(){}observe(){}},CustomEvent:class{}};
vm.createContext(ctx);for(const f of ['locale-data.js','i18n.js'])vm.runInContext(fs.readFileSync(path.join(web,f),'utf8'),ctx);
assert.equal(ui.nodeValue,'Settings');assert.equal(dynamic.nodeValue,'Generating 3/40');assert.equal(effort.nodeValue,'Off');
assert.equal(input.getAttribute('placeholder'),'Send a message…');
for(const [node,value] of [[user,'模型设置'],[title,'新会话'],[stream,'正在思考']])assert.equal(node.nodeValue,value);
ctx.window.StudioI18n.setLanguage('zh');assert.equal(ui.nodeValue,'模型设置');assert.equal(dynamic.nodeValue,'正在生成 3/40');assert.equal(effort.nodeValue,'关闭');
ctx.window.StudioI18n.setLanguage('en');assert.equal(ctx.window.t('预计剩余 12 分钟'),'About 12 min remaining');assert.equal(ctx.window.t('预计剩余 2 小时 3 分钟'),'About 2 h 3 min remaining');assert.equal(ctx.window.t('768 × 768　40 步　186 秒'),'768 × 768　40 steps　186 s');
// A later status update must replace the saved source, not restore stale text.
dynamic.nodeValue='正在生成 4/40';ctx.window.StudioI18n.render();assert.equal(dynamic.nodeValue,'Generating 4/40');ctx.window.StudioI18n.setLanguage('zh');assert.equal(dynamic.nodeValue,'正在生成 4/40');
assert.deepEqual(JSON.parse(JSON.stringify(ctx.window.STUDIO_MESSAGES)),JSON.parse(fs.readFileSync(path.join(web,'locales.json'),'utf8')));
assert.deepEqual(JSON.parse(JSON.stringify(ctx.window.STUDIO_PATTERNS)),JSON.parse(fs.readFileSync(path.join(web,'locale-patterns.json'),'utf8')));
console.log('PASS: language switching, dynamic text, catalog sync and user text preservation');
