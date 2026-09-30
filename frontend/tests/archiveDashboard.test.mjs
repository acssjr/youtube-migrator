import test from 'node:test';
import assert from 'node:assert/strict';
import { buildArchivePending, playlistIds } from '../src/services/archiveDashboard.mjs';
const video = overrides => ({ id: 'abcdefghijk', title: 'Marcha', description: 'Texto', composer: 'Autor', work: 'Obra', ensemble: 'União Sanfelixta', catalog_ambiguous: false, events: [], ...overrides });
const record = (kind, payload, date = '2026-09-30') => ({ id: kind + date, kind, payload, created_at: date, updated_at: date });
test('Playlist recognition excludes unrelated hosts and preserves IDs', () => {
  assert.deepEqual([...playlistIds('https://evil.test/?list=no https://www.youtube.com/playlist?list=PL123&index=2 https://youtu.be/abcdefghijk?list=PL123')], ['PL123']);
});
test('Original gaps only exist after inventory and use explicit video bindings', () => {
  assert.equal(buildArchivePending([video()], [], 'canal').originals, null);
  assert.deepEqual(buildArchivePending([video()], [record('original', { files: [{ videoId: 'abcdefghijk' }] })], 'canal').originals, []);
  assert.equal(buildArchivePending([video()], [record('original', { files: [{ videoId: 'otherchannel' }] })], 'canal').originalCount, 0);
  assert.equal(buildArchivePending([video()], [record('original', { files: 'incomplete import' })], 'canal').originals.length, 1);
});
test('Latest compatible footer wins without assigning another ensemble or project', () => {
  const records = [record('footer', { ensemble: 'Outra Banda', text: 'https://youtube.com/playlist?list=WRONG' }), record('footer', { ensemble: 'União Sanfelixta', project: 'Retreta', text: 'https://youtube.com/playlist?list=RETRETA' }), record('footer', { ensemble: 'União Sanfelixta', text: 'https://youtube.com/playlist?list=NEW' }), record('footer', { ensemble: 'União Sanfelixta', text: 'https://youtube.com/playlist?list=OLD' }, '2025-01-01')];
  assert.equal(buildArchivePending([video({ description: 'https://youtube.com/playlist?list=NEW' })], records, 'canal').outdated.length, 0);
  assert.equal(buildArchivePending([video({ description: 'https://youtube.com/playlist?list=OLD' })], records, 'canal').outdated.length, 1);
});
test('Catalog diagnostics are channel scoped and preserve missing event dates', () => {
  const summary = buildArchivePending([video({ composer: '', description: '', catalog_ambiguous: true })], [record('event', { name: 'Ontem', performed_at: '', channel_id: 'canal' }), record('event', { name: 'Outro', performed_at: '', channel_id: 'outro' })], 'canal');
  assert.equal(summary.blank.length, 1); assert.equal(summary.credits.length, 1); assert.equal(summary.ambiguous.length, 1); assert.equal(summary.undated.length, 1);
});
