import test from 'node:test';
import assert from 'node:assert/strict';
import { hashBlob, copyBlob, safeRelativePath, manifestChunks } from '../src/services/originalArchive.mjs';

test('SHA-256 reads bounded slices and agrees with known digest', async () => {
  assert.equal(await hashBlob(new Blob(['abc'])), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
  const blob = new Blob([new Uint8Array(9 * 1024 * 1024)]); const sizes = [];
  const source = { size: blob.size, slice(start, end) { sizes.push(end - start); return blob.slice(start, end); } };
  await hashBlob(source); assert.equal(sizes.length, 3); assert.ok(sizes.every(size => size <= 4 * 1024 * 1024));
});
test('reject traversal and absolute paths', () => {
  for (const value of ['../video.mp4', '/video.mp4', 'folder//video.mp4', 'folder/./video.mp4']) assert.throws(() => safeRelativePath(value));
  assert.deepEqual(safeRelativePath('Retreta/Noite 5/video.mp4'), ['Retreta', 'Noite 5', 'video.mp4']);
});
test('split metadata into bounded chunks without losing files', () => {
  const files = Array.from({ length: 100 }, (_, i) => ({ path: `video-${i}.mp4`, text: 'á'.repeat(500) }));
  const chunks = manifestChunks(files, { name: 'Retreta' }, 5000);
  assert.deepEqual(chunks.flatMap(chunk => chunk.files), files);
  assert.ok(chunks.every(chunk => new TextEncoder().encode(JSON.stringify(chunk)).length <= 5000));
});
test('cancel copy aborts writable instead of committing incomplete content', async () => {
  const controller = new AbortController(); let closed = false; let aborted = false; let chunks = 0;
  const writer = { async write() { chunks++; controller.abort(); }, async close() { closed = true; }, async abort() { aborted = true; } };
  await assert.rejects(copyBlob(new Blob([new Uint8Array(9 * 1024 * 1024)]), { async createWritable() { return writer; } }, controller.signal));
  assert.equal(chunks, 1); assert.equal(closed, false); assert.equal(aborted, true);
});
