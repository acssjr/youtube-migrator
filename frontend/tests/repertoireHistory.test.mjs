import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
const source = await readFile(new URL('../src/services/repertoireHistory.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } });
const { groupRepertoire } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const item = (id, overrides = {}) => ({ id, title: 'Marcha Aurora', work: 'Aurora', composer: 'José', arranger: '', genre: 'Marcha', ensemble: 'Filarmônica A', published_at: '2026-09-01', events: [], ...overrides });

test('keeps distinct arrangers and unidentified authors separate', () => {
  assert.equal(groupRepertoire([item('1'), item('2', { arranger: 'Maria' })]).length, 2);
  assert.equal(groupRepertoire([item('1', { composer: '' }), item('2', { composer: '' })]).length, 2);
});
test('normalizes accents and groups repeated recordings without assuming performance dates', () => {
  const [group] = groupRepertoire([item('1'), item('2', { composer: 'JOSE' })]);
  assert.equal(group.recordings.length, 2);
  assert.deepEqual(group.performedDates, []);
  assert.deepEqual(group.publishedDates, ['2026-09-01']);
});
test('registered ensemble overrides parsed title and keeps performance dates independent', () => {
  const groups = groupRepertoire([item('1', { events: [{ ensemble: 'Filarmônica B', performed_at: '2023-06-04', name: 'Retreta' }] })]);
  assert.equal(groups[0].ensemble, 'Filarmônica B');
  assert.deepEqual(groups[0].performedDates, ['2023-06-04']);
  assert.deepEqual(groups[0].publishedDates, ['2026-09-01']);
});
test('deduplicates a recording with multiple events from the same ensemble', () => {
  const event = { ensemble: 'Filarmônica A', performed_at: '2023-06-04', name: 'Retreta' };
  const [group] = groupRepertoire([item('1', { events: [event, event] })]);
  assert.equal(group.recordings.length, 1);
  assert.deepEqual(group.performedDates, ['2023-06-04']);
});
