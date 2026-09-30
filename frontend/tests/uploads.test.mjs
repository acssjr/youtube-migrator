import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

async function load(name) {
  const source = await readFile(new URL(`../src/services/${name}.ts`, import.meta.url), 'utf8');
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
}
const { sendUpload, validateSessionUrl } = await load('uploadTransport');
const { composeUploadTitle } = await load('uploadMetadata');
const session = 'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=test';
const reply = (status, text = '', headers = {}) => ({ status, text, header: name => headers[name] || null });
const done = reply(201, JSON.stringify({ id: 'uploaded', status: { privacyStatus: 'private' } }));
function options(overrides = {}) {
  return { file: new Blob([new Uint8Array(10 * 1024 * 1024)], { type: 'video/mp4' }),
    metadata: { snippet: { title: 'Title', description: '', categoryId: '10' }, status: { privacyStatus: 'private', selfDeclaredMadeForKids: false } },
    signal: new AbortController().signal, getToken: async () => 'temporary', onSession: () => {}, onCheckpoint: () => {}, onProgress: () => {}, delay: async () => {}, ...overrides };
}

test('titles use selected names and never emit empty separators', () => {
  const item = { genre: 'Dobrado', ensemble: 'Sociedade Filarmônica 25 de Março', identity: { work: 'Allah', composer: 'Estevam Moura', arranger: '' } };
  assert.equal(composeUploadTitle(item), 'Dobrado Allah — Estevam Moura — Sociedade Filarmônica 25 de Março');
  assert.equal(composeUploadTitle({ ...item, genre: '', ensemble: '', identity: { work: 'Allah', composer: '', arranger: '' } }), 'Allah');
  assert.equal(composeUploadTitle({ ...item, identity: { ...item.identity, work: '' } }), '');
});
test('uploads aligned chunks and confirms actual privacy', async () => {
  const requests = []; const checkpoints = []; const sessions = [];
  const responses = [reply(200, '', { Location: session }), reply(308, '', { Range: 'bytes=0-8388607' }), done];
  const result = await sendUpload(options({ onSession: url => sessions.push(url), onCheckpoint: n => checkpoints.push(n), request: async (...args) => { requests.push(args); return responses.shift(); } }));
  assert.equal(requests[1][2]['Content-Range'], 'bytes 0-8388607/10485760');
  assert.equal(requests[2][2]['Content-Range'], 'bytes 8388608-10485759/10485760');
  assert.equal(result.privacy, 'private');
  assert.deepEqual(checkpoints, [8388608, 10485760]);
  assert.deepEqual(sessions, [session]);
});
test('lost final response is checked without creating a second video', async () => {
  const requests = [];
  const responses = [reply(200, '', { Location: session }), reply(308, '', { Range: 'bytes=0-8388607' }), reply(0), done];
  const result = await sendUpload(options({ request: async (...args) => { requests.push(args); return responses.shift(); } }));
  assert.equal(result.id, 'uploaded');
  assert.equal(requests.filter(r => r[0] === 'POST').length, 1);
  assert.equal(requests.at(-1)[2]['Content-Range'], 'bytes */10485760');
  assert.equal(requests.at(-1)[3], null);
});
test('restored sessions query the authoritative offset before sending', async () => {
  const requests = [];
  const responses = [reply(308, '', { Range: 'bytes=0-8388607' }), done];
  await sendUpload(options({ sessionUrl: session, request: async (...args) => { requests.push(args); return responses.shift(); } }));
  assert.equal(requests[0][2]['Content-Range'], 'bytes */10485760');
  assert.equal(requests[1][2]['Content-Range'], 'bytes 8388608-10485759/10485760');
  assert.ok(requests.every(r => r[0] === 'PUT'));
});
test('expired sessions fail without automatically restarting', async () => {
  let requests = 0;
  await assert.rejects(sendUpload(options({ sessionUrl: session, request: async () => { requests++; return reply(404); } })), /sessão expirou/);
  assert.equal(requests, 1);
});
test('refreshes expired authorization and probes the session', async () => {
  let tokens = 0; const requests = [];
  const responses = [reply(401), reply(308), reply(308, '', { Range: 'bytes=0-8388607' }), done];
  await sendUpload(options({ sessionUrl: session, getToken: async () => `token-${++tokens}`, request: async (...args) => { requests.push(args); return responses.shift(); } }));
  assert.equal(tokens, 2);
  assert.equal(requests[1][2].Authorization, 'Bearer token-2');
});
test('pausing before authorization completes never starts a session', async () => {
  const controller = new AbortController(); let requests = 0;
  await assert.rejects(sendUpload(options({ signal: controller.signal, getToken: async () => { controller.abort(); return 'token'; }, request: async () => { requests++; return done; } })), error => error.name === 'AbortError');
  assert.equal(requests, 0);
});
test('refuses untrusted upload destinations', () => {
  assert.throws(() => validateSessionUrl('https://other.test/upload/youtube/v3/videos?upload_id=x'), /inválida/);
});
test('does not loop forever when YouTube acknowledges bytes but not completion', async () => {
  let requests = 0;
  await assert.rejects(sendUpload(options({ sessionUrl: session, request: async () => { requests++; return reply(308, '', { Range: 'bytes=0-10485759' }); } })), /ainda não confirmou/);
  assert.equal(requests, 6);
});

async function queueHarness(saved = null) {
  const dataUrl = text => `data:text/javascript;base64,${Buffer.from(text).toString('base64')}`;
  const storage = new Map(saved ? [['acervo-upload-queue-v1', JSON.stringify(saved)]] : []);
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value) } });
  globalThis.window = { addEventListener() {} };
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: {} });
  const fakeUrl = dataUrl(`export const calls = []; export const control = { fail: false }; export async function sendUpload(options) {
    calls.push(options); if (control.fail) throw new Error('quota');
    options.onSession('https://www.googleapis.com/upload/youtube/v3/videos?upload_id=test');
    options.onCheckpoint(options.file.size);
    return { id: 'video-' + calls.length, privacy: options.metadata.status.privacyStatus };
  } // ${Math.random()}`);
  const fake = await import(fakeUrl);
  const source = await readFile(new URL('../src/services/uploadQueue.ts', import.meta.url), 'utf8');
  let compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  compiled = compiled.replace(/from ['"]\.\/api['"]/g, `from '${dataUrl("export const api = { uploads: { authorize: async () => ({access_token: 'temporary'}) } };")}'`)
    .replace(/from ['"]\.\/uploadTransport['"]/g, `from '${fakeUrl}'`)
    .replace(/from ['"]\.\/uploadMetadata['"]/g, `from '${dataUrl('export const composeUploadTitle = () => "";')}'`);
  const { uploadQueue } = await import(dataUrl(compiled + `\n// ${Math.random()}`));
  return { uploadQueue, fake, storage };
}
function prepare(queue, count = 2) {
  queue.add(Array.from({ length: count }, (_, i) => new File(['video'], `${i}.mp4`, { type: 'video/mp4', lastModified: 10 })), 'private', 'channel');
  queue.snapshot().items.forEach(item => queue.patch(item.id, { title: item.name, identity: { work: item.name, composer: '', arranger: '' } }));
}
test('queue uploads once per file and never reuploads completed items', async () => {
  const { uploadQueue, fake, storage } = await queueHarness(); prepare(uploadQueue);
  await uploadQueue.start();
  assert.equal(fake.calls.length, 2);
  assert.ok(uploadQueue.snapshot().items.every(item => item.status === 'completed' && !item.sessionUrl));
  await assert.rejects(uploadQueue.start(), /Selecione um canal/);
  assert.equal(fake.calls.length, 2);
  assert.ok(!storage.get('acervo-upload-queue-v1').includes('temporary'));
});
test('a failed file stops the queue before later files', async () => {
  const { uploadQueue, fake } = await queueHarness(); prepare(uploadQueue); fake.control.fail = true;
  await uploadQueue.start();
  assert.equal(fake.calls.length, 1);
  assert.deepEqual(uploadQueue.snapshot().items.map(item => item.status), ['error', 'draft']);
  assert.equal(uploadQueue.snapshot().running, false);
});
test('missing files after reload require matching original selection', async () => {
  const initial = await queueHarness(); prepare(initial.uploadQueue, 1);
  const saved = JSON.parse(initial.storage.get('acervo-upload-queue-v1'));
  saved.items[0].status = 'uploading'; saved.items[0].sessionUrl = session;
  const { uploadQueue, fake } = await queueHarness(saved);
  assert.equal(uploadQueue.snapshot().items[0].status, 'paused');
  await assert.rejects(uploadQueue.start(), /Selecione novamente/);
  uploadQueue.add([new File(['video'], '0.mp4', { type: 'video/mp4', lastModified: 10 })], 'public', 'other-channel');
  assert.equal(uploadQueue.snapshot().items.length, 1);
  await uploadQueue.start();
  assert.equal(fake.calls[0].sessionUrl, session);
  assert.equal(fake.calls[0].metadata.status.privacyStatus, 'private');
  assert.equal(uploadQueue.snapshot().channelId, 'channel');
});
test('another tab holding the upload lock prevents duplicate sends', async () => {
  const { uploadQueue, fake } = await queueHarness(); prepare(uploadQueue, 1);
  navigator.locks = { request: async (_, __, callback) => callback(null) };
  await assert.rejects(uploadQueue.start(), /outra aba/);
  assert.equal(fake.calls.length, 0);
});
