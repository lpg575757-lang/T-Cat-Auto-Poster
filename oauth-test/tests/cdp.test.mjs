import assert from 'node:assert/strict';
import test from 'node:test';

import {CdpClient, assertSandboxContext, sanitizeDisplayUrl, validateEndpoint} from '../cdp.mjs';

class FakeSocket extends EventTarget {
  constructor(handler) { super(); this.handler = handler; this.readyState = 1; }
  send(raw) {
    const command = JSON.parse(raw);
    queueMicrotask(() => {
      const result = this.handler(command);
      this.dispatchEvent(new MessageEvent('message', {data: JSON.stringify({id: command.id, ...result})}));
    });
  }
  close() { this.readyState = 3; }
}

test('correlates commands and inspects page text', async () => {
  const socket = new FakeSocket(command => ({result: {result: {value: {url: 'https://developers.tiktok.com/apps', text: 'Sandbox T Cat Sandbox'}}}}));
  const client = new CdpClient(socket);
  const [first, second] = await Promise.all([client.inspectPage(), client.inspectPage()]);
  assert.equal(first.text, 'Sandbox T Cat Sandbox');
  assert.equal(second.url, 'https://developers.tiktok.com/apps');
});

test('selector failures are safe and precise', async () => {
  const socket = new FakeSocket(() => ({result: {result: {value: {ok: false, code: 'selector_not_found'}}}}));
  const client = new CdpClient(socket);
  await assert.rejects(client.click('#missing'), /selector_not_found/);
});

test('requires loopback endpoint and exact Sandbox context', () => {
  assert.equal(validateEndpoint('http://127.0.0.1:9333'), 'http://127.0.0.1:9333');
  assert.throws(() => validateEndpoint('http://example.com:9333'), /loopback_required/);
  assert.doesNotThrow(() => assertSandboxContext({mode: 'Sandbox', sandboxName: 'T Cat Sandbox'}));
  assert.throws(() => assertSandboxContext({mode: 'Production', sandboxName: 'T Cat Sandbox'}), /sandbox_guard_failed/);
  assert.throws(() => assertSandboxContext({mode: 'Sandbox', sandboxName: 'Other'}), /sandbox_guard_failed/);
});

test('file upload uses CDP DOM command only after Sandbox guard', async () => {
  const methods = [];
  const socket = new FakeSocket(command => {
    methods.push(command.method);
    if (command.method === 'DOM.getDocument') return {result: {root: {nodeId: 1}}};
    if (command.method === 'DOM.querySelector') return {result: {nodeId: 9}};
    return {result: {}};
  });
  const client = new CdpClient(socket);
  await client.setFileInput('input[type=file]', 'C:/approved/icon.png', {mode: 'Sandbox', sandboxName: 'T Cat Sandbox'});
  assert.deepEqual(methods, ['DOM.getDocument', 'DOM.querySelector', 'DOM.setFileInputFiles']);
  await assert.rejects(client.setFileInput('input', 'C:/x', {mode: 'Production', sandboxName: 'T Cat Sandbox'}), /sandbox_guard_failed/);
});

test('navigation allows only TikTok HTTPS and the fixed local callback origin', async () => {
  const socket = new FakeSocket(() => ({result: {}}));
  const client = new CdpClient(socket);
  await client.navigate('http://127.0.0.1:3455/');
  await assert.rejects(client.navigate('http://127.0.0.1:9999/'), /navigation_host_not_allowed/);
  await assert.rejects(client.navigate('https://example.com/'), /navigation_host_not_allowed/);
});

test('safe inspection never returns query or fragment', async () => {
  const socket = new FakeSocket(() => ({result: {result: {value: {url: 'http://127.0.0.1:3455/callback/', text: 'ok'}}}}));
  const page = await new CdpClient(socket).inspectPageSafe();
  assert.equal(page.url, 'http://127.0.0.1:3455/callback/');
  assert.equal(page.url.includes('?'), false);
  assert.equal(page.url.includes('#'), false);
});

test('displayed tab URLs always discard query and fragment', () => {
  assert.equal(sanitizeDisplayUrl('http://127.0.0.1:3455/callback/?code=hidden&state=hidden#x'), 'http://127.0.0.1:3455/callback/');
});
