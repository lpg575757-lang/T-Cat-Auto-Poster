import {writeFileSync} from 'node:fs';

const LOOPBACK = new Set(['127.0.0.1', 'localhost', '[::1]']);

export function sanitizeDisplayUrl(raw) {
  const url = new URL(raw);
  return url.origin + url.pathname;
}

export function validateEndpoint(raw) {
  let endpoint;
  try { endpoint = new URL(raw); } catch { throw new Error('cdp_endpoint_invalid'); }
  if (endpoint.protocol !== 'http:' || !LOOPBACK.has(endpoint.hostname) || !endpoint.port) {
    throw new Error('loopback_required');
  }
  return endpoint.origin;
}

export function assertSandboxContext(context) {
  if (context?.mode !== 'Sandbox' || context?.sandboxName !== 'T Cat Sandbox') {
    throw new Error('sandbox_guard_failed');
  }
}

export class CdpClient {
  constructor(socket) {
    this.socket = socket;
    this.nextId = 1;
    this.pending = new Map();
    socket.addEventListener('message', event => {
      const message = JSON.parse(event.data);
      if (!message.id || !this.pending.has(message.id)) return;
      const {resolve, reject} = this.pending.get(message.id);
      this.pending.delete(message.id);
      if (message.error) reject(new Error(`cdp_error:${message.error.code}`));
      else resolve(message.result);
    });
  }

  command(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, {resolve, reject});
      this.socket.send(JSON.stringify({id, method, params}));
    });
  }

  async evaluate(expression) {
    const result = await this.command('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
    if (result.exceptionDetails) throw new Error('page_evaluation_failed');
    return result.result?.value;
  }

  inspectPage() {
    return this.inspectPageSafe();
  }

  inspectPageSafe() {
    return this.evaluate(`(() => ({url: location.origin + location.pathname, text: document.body?.innerText || ''}))()`);
  }

  inspectLinks() {
    return this.evaluate(`(() => [...document.querySelectorAll('a')].map(a => ({text:(a.innerText||a.getAttribute('aria-label')||'').trim(),href:a.href})).filter(x=>x.text||x.href))()`);
  }

  inspectInteractives() {
    return this.evaluate(`(() => [...document.querySelectorAll('button,[role="button"],[role="link"],input,select')].map((e,i)=>({index:i,tag:e.tagName,type:e.getAttribute('type')||'',text:(e.innerText||e.value||e.getAttribute('aria-label')||'').trim(),disabled:!!e.disabled})).filter(x=>x.text))()`);
  }

  inspectRows() {
    return this.evaluate(`(() => [...document.querySelectorAll('tr')].map((e,i)=>({index:i,text:(e.innerText||'').trim()})).filter(x=>x.text))()`);
  }

  inspectInputs() {
    return this.evaluate(`(() => [...document.querySelectorAll('input,textarea,select')].map((e,i)=>{const name=e.getAttribute('name')||'';const sensitive=/secret|token|code|authorization/i.test(name);return {index:i,tag:e.tagName,type:e.getAttribute('type')||'',name,placeholder:e.getAttribute('placeholder')||'',aria:e.getAttribute('aria-label')||'',checked:e.type==='checkbox'?e.checked:undefined,value:(!sensitive&&['text','TEXTAREA','SELECT'].includes(e.type||e.tagName))?e.value:undefined}}))()`);
  }

  inspectLabels() {
    return this.evaluate(`(() => [...document.querySelectorAll('label')].map((e,i)=>({index:i,text:(e.innerText||'').trim(),for:e.htmlFor||''})).filter(x=>x.text))()`);
  }

  inspectButtons() {
    return this.evaluate(`(() => [...document.querySelectorAll('button')].map((e,i)=>{const r=e.getBoundingClientRect();return {index:i,text:(e.innerText||'').trim(),aria:e.getAttribute('aria-label')||'',title:e.getAttribute('title')||'',className:e.className||'',x:Math.round(r.x),y:Math.round(r.y),width:Math.round(r.width),height:Math.round(r.height)}}))()`);
  }

  inspectRoles() {
    return this.evaluate(`(() => [...document.querySelectorAll('[role]')].map((e,i)=>({index:i,role:e.getAttribute('role'),text:(e.innerText||e.getAttribute('aria-label')||'').trim()})).filter(x=>x.text))()`);
  }

  async setFileInput(selector, filePath, context) {
    assertSandboxContext(context);
    const document = await this.command('DOM.getDocument', {depth: 0});
    const found = await this.command('DOM.querySelector', {nodeId: document.root.nodeId, selector});
    if (!found.nodeId) throw new Error('file_input_not_found');
    await this.command('DOM.setFileInputFiles', {nodeId: found.nodeId, files: [filePath]});
  }

  async clickText(text, context) {
    if (context) assertSandboxContext(context);
    const value = await this.evaluate(`(() => { const wanted=${JSON.stringify(text)}; const items=[...document.querySelectorAll('a,button,[role="button"],[role="link"],[role="option"],tr')].filter(e=>(e.innerText||'').trim()===wanted); if(items.length!==1)return {ok:false,code:items.length?'text_not_unique':'text_not_found'}; items[0].click(); return {ok:true}; })()`);
    if (!value?.ok) throw new Error(value?.code || 'text_action_failed');
  }

  async navigate(url) {
    const parsed = new URL(url);
    const tiktok = parsed.protocol === 'https:' && ['developers.tiktok.com', 'www.tiktok.com'].includes(parsed.hostname);
    const local = parsed.protocol === 'http:' && parsed.hostname === '127.0.0.1' && parsed.port === '3455';
    if (!tiktok && !local) {
      throw new Error('navigation_host_not_allowed');
    }
    await this.command('Page.navigate', {url: parsed.href});
  }

  async captureScreenshot(path) {
    const result = await this.command('Page.captureScreenshot', {format: 'png', captureBeyondViewport: false});
    writeFileSync(path, Buffer.from(result.data, 'base64'));
  }

  async click(selector, context) {
    if (context) assertSandboxContext(context);
    const value = await this.evaluate(`(() => { const e=document.querySelector(${JSON.stringify(selector)}); if(!e)return {ok:false,code:'selector_not_found'}; e.click(); return {ok:true}; })()`);
    if (!value?.ok) throw new Error(value?.code || 'selector_action_failed');
  }

  async fill(selector, value, context) {
    if (context) assertSandboxContext(context);
    const result = await this.evaluate(`(() => { const e=document.querySelector(${JSON.stringify(selector)}); if(!e)return {ok:false,code:'selector_not_found'}; e.focus(); e.value=${JSON.stringify(value)}; e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true})); return {ok:true}; })()`);
    if (!result?.ok) throw new Error(result?.code || 'selector_action_failed');
  }

  async fillAt(selector, index, value, context) {
    assertSandboxContext(context);
    const result = await this.evaluate(`(() => { const e=document.querySelectorAll(${JSON.stringify(selector)})[${Number(index)}]; if(!e)return {ok:false,code:'field_not_found'}; const proto=e instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(proto,'value').set.call(e,${JSON.stringify(value)}); e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true})); return {ok:true}; })()`);
    if (!result?.ok) throw new Error(result?.code || 'field_action_failed');
  }

  async setCheckboxAt(index, checked, context) {
    assertSandboxContext(context);
    const result = await this.evaluate(`(() => { const e=document.querySelectorAll('input[type="checkbox"]')[${Number(index)}]; if(!e)return {ok:false,code:'checkbox_not_found'}; if(e.checked!==${Boolean(checked)})e.click(); return {ok:true,checked:e.checked}; })()`);
    if (!result?.ok || result.checked !== Boolean(checked)) throw new Error(result?.code || 'checkbox_action_failed');
  }

  async addProduct(name, context) {
    assertSandboxContext(context);
    const result = await this.evaluate(`(() => { const wanted=${JSON.stringify(name)}; const matches=[...document.querySelectorAll('div,span,p,h1,h2,h3,h4')].filter(e=>(e.innerText||'').trim()===wanted).sort((a,b)=>a.children.length-b.children.length); if(!matches.length)return {ok:false,code:'product_not_found'}; let node=matches[0]; for(let i=0;i<8&&node;i++,node=node.parentElement){const button=[...node.querySelectorAll('button')].find(b=>(b.innerText||'').trim()==='Add'&&!b.disabled);if(button){button.click();return {ok:true};}} return {ok:false,code:'product_add_unavailable'}; })()`);
    if (!result?.ok) throw new Error(result?.code || 'product_action_failed');
  }

  close() { this.socket.close(); }
}

export async function listTabs(endpoint) {
  const base = validateEndpoint(endpoint);
  const response = await fetch(`${base}/json/list`);
  if (!response.ok) throw new Error(`cdp_list_failed:${response.status}`);
  const tabs = await response.json();
  return tabs.filter(tab => tab.type === 'page').map(({id, title, url, webSocketDebuggerUrl}) => ({id, title, url, webSocketDebuggerUrl}));
}

export async function connectToTab(endpoint, tabId) {
  const tabs = await listTabs(endpoint);
  const tab = tabId ? tabs.find(item => item.id === tabId) : tabs[0];
  if (!tab?.webSocketDebuggerUrl) throw new Error('cdp_page_not_found');
  const socket = new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, {once: true});
    socket.addEventListener('error', () => reject(new Error('cdp_connection_failed')), {once: true});
  });
  return new CdpClient(socket);
}

async function main() {
  const [action = 'inspect', argument] = process.argv.slice(2);
  const endpoint = validateEndpoint(process.env.CDP_ENDPOINT || 'http://127.0.0.1:9333');
  if (action === 'tabs') {
    const tabs = await listTabs(endpoint);
    console.log(JSON.stringify(tabs.map(({id, title, url}) => ({id, title, url:sanitizeDisplayUrl(url)}))));
    return;
  }
  const client = await connectToTab(endpoint, process.env.CDP_TAB_ID);
  try {
    if (action === 'inspect') console.log(JSON.stringify(await client.inspectPage()));
    else if (action === 'safe-inspect') console.log(JSON.stringify(await client.inspectPageSafe()));
    else if (action === 'links') console.log(JSON.stringify(await client.inspectLinks()));
    else if (action === 'interactives') console.log(JSON.stringify(await client.inspectInteractives()));
    else if (action === 'rows') console.log(JSON.stringify(await client.inspectRows()));
    else if (action === 'inputs') console.log(JSON.stringify(await client.inspectInputs()));
    else if (action === 'labels') console.log(JSON.stringify(await client.inspectLabels()));
    else if (action === 'buttons') console.log(JSON.stringify(await client.inspectButtons()));
    else if (action === 'roles') console.log(JSON.stringify(await client.inspectRoles()));
    else if (action === 'sandbox-upload') {
      const page = await client.inspectPage();
      if (!page.url.includes('/sandbox/') || !page.text.includes('You are editing T Cat Sandbox')) throw new Error('sandbox_guard_failed');
      await client.setFileInput('input[type="file"]', argument, {mode:'Sandbox', sandboxName:'T Cat Sandbox'});
    }
    else if (action === 'sandbox-click-selector') {
      const page = await client.inspectPage();
      if (!page.url.includes('/sandbox/') || !page.text.includes('You are editing T Cat Sandbox')) throw new Error('sandbox_guard_failed');
      await client.click(argument, {mode:'Sandbox', sandboxName:'T Cat Sandbox'});
    }
    else if (action === 'sandbox-click-text') {
      const page = await client.inspectPage();
      if (!page.url.includes('/sandbox/') || !page.text.includes('You are editing T Cat Sandbox')) throw new Error('sandbox_guard_failed');
      await client.clickText(argument, {mode:'Sandbox', sandboxName:'T Cat Sandbox'});
    }
    else if (action === 'sandbox-fill-basic') {
      const page = await client.inspectPage();
      if (!page.url.includes('/sandbox/') || !page.text.includes('You are editing T Cat Sandbox')) throw new Error('sandbox_guard_failed');
      const context={mode:'Sandbox',sandboxName:'T Cat Sandbox'};
      await client.fillAt('textarea:not([aria-label="Message input"])',0,'T Cat Auto Poster helps creators organize their own videos and prepare them for publishing with user authorization.',context);
      await client.fillAt('input[type="text"]',1,'https://lpg575757-lang.github.io/T-Cat-Auto-Poster/terms.html',context);
      await client.fillAt('input[type="text"]',2,'https://lpg575757-lang.github.io/T-Cat-Auto-Poster/privacy.html',context);
      await client.setCheckboxAt(0,false,context);
      await client.setCheckboxAt(1,true,context);
      await client.setCheckboxAt(2,false,context);
      await client.setCheckboxAt(3,false,context);
    }
    else if (action === 'sandbox-fill-site-url') {
      const page = await client.inspectPage();
      if (!page.url.includes('/sandbox/') || !page.text.includes('You are editing T Cat Sandbox')) throw new Error('sandbox_guard_failed');
      await client.fillAt('input[type="text"]',3,'https://lpg575757-lang.github.io/T-Cat-Auto-Poster/',{mode:'Sandbox',sandboxName:'T Cat Sandbox'});
    }
    else if (action === 'sandbox-add-product') {
      const page = await client.inspectPage();
      if (!page.url.includes('/sandbox/') || !page.text.includes('You are editing T Cat Sandbox')) throw new Error('sandbox_guard_failed');
      await client.addProduct(argument,{mode:'Sandbox',sandboxName:'T Cat Sandbox'});
    }
    else if (action === 'sandbox-add-content-posting') {
      const page = await client.inspectPage();
      if (!page.url.includes('/sandbox/') || !page.text.includes('You are editing T Cat Sandbox')) throw new Error('sandbox_guard_failed');
      const result=await client.evaluate(`(() => {const buttons=[...document.querySelectorAll('button.css-y1m958')];const button=buttons[2];if(!button||button.disabled||(button.innerText||'').trim()!=='Add')return {ok:false,code:'content_posting_add_unavailable'};button.click();return {ok:true};})()`);
      if(!result?.ok)throw new Error(result?.code||'content_posting_action_failed');
    }
    else if (action === 'sandbox-configure-products') {
      const page = await client.inspectPage();
      if (!page.url.includes('/sandbox/') || !page.text.includes('You are editing T Cat Sandbox')) throw new Error('sandbox_guard_failed');
      const context={mode:'Sandbox',sandboxName:'T Cat Sandbox'};
      await client.fillAt('input[type="text"]',4,'http://127.0.0.1:3455/callback/',context);
      await client.setCheckboxAt(4,true,context);
    }
    else if (action === 'screenshot') await client.captureScreenshot(argument);
    else if (action === 'scroll') await client.evaluate(`window.scrollTo(0, ${Number(argument) || 0})`);
    else if (action === 'sanitize-local-url') {
      const page=await client.inspectPage();
      if(!page.url.startsWith('http://127.0.0.1:3455/callback/'))throw new Error('local_callback_required');
      await client.evaluate(`history.replaceState(null,'','/authorized')`);
    }
    else if (action === 'local-review') {
      const page=await client.inspectPage();
      if(page.url!=='http://127.0.0.1:3455/authorized')throw new Error('authorized_local_page_required');
      const result=await client.evaluate(`(() => {const set=(name,value)=>{const e=document.querySelector('input[name="'+name+'"]');if(!e)return false;Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,value);e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return true;};return {ok:set('path',${JSON.stringify(argument)})&&set('caption','T Cat Auto Poster Sandbox Direct Post test')};})()`);
      if(!result?.ok)throw new Error('review_fields_not_found');
      await client.clickText('Review');
    }
    else if (action === 'click-text') await client.clickText(argument);
    else if (action === 'navigate') await client.navigate(argument);
    else throw new Error('unsupported_action');
  } finally { client.close(); }
}

if (import.meta.url === `file:///${process.argv[1]?.replaceAll('\\', '/')}`) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
