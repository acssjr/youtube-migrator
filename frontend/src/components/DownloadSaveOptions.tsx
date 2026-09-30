import { useState } from 'react';
import { FolderOpen } from 'lucide-react';
import { DownloadJob } from '../types';

interface WritableFile { write(data: Uint8Array): Promise<void>; close(): Promise<void>; abort(): Promise<void> }
interface DirectoryHandle {
  name: string;
  queryPermission(options: { mode: 'readwrite' }): Promise<string>;
  requestPermission(options: { mode: 'readwrite' }): Promise<string>;
  getFileHandle(name: string, options?: { create?: boolean }): Promise<{ createWritable(): Promise<WritableFile> }>;
}
export interface SaveOptions { pattern: string; collision: 'number' | 'confirm'; directory?: DirectoryHandle }
const storageKey = 'acervo-download-save-options-v1';
let currentOptions: SaveOptions = { pattern: '{titulo}', collision: 'number' };
try {
  const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
  if (typeof saved.pattern === 'string') currentOptions.pattern = saved.pattern;
  if (saved.collision === 'confirm') currentOptions.collision = 'confirm';
} catch { /* An unavailable preference store does not prevent saving files. */ }

export function preparedFileName(job: DownloadJob, pattern = '{titulo}') {
  const parts = job.title.split(/\s+[—–]\s+/).map(part => part.trim()).filter(Boolean);
  // Only infer the known institutional title layout. Other titles remain intact.
  const structured = parts.length >= 3 && /filarm[oô]nica/i.test(parts[parts.length - 1]);
  const values: Record<string, string> = {
    titulo: job.title || job.video_id, id: job.video_id,
    obra: structured ? parts[0] : job.title,
    compositor: structured ? parts[1] : '',
    filarmonica: structured ? parts[parts.length - 1] : '',
  };
  let name = pattern.replace(/\{(titulo|id|obra|compositor|filarmonica)\}/g, (_, key: string) => values[key]);
  name = name.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '-').replace(/\s+/g, ' ').replace(/(?:\s+[—–-]\s*)+$/g, '').trim().replace(/[. ]+$/g, '');
  if (!name) name = job.title.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '-').trim() || job.video_id;
  name = name.slice(0, 175).replace(/[. ]+$/g, '');
  if (/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(name)) name = '_' + name;
  return `${name}.${job.format}`;
}

async function exists(directory: DirectoryHandle, name: string) {
  try { await directory.getFileHandle(name); return true; }
  catch (error) { if (error instanceof DOMException && error.name === 'NotFoundError') return false; throw error; }
}

let saveTail: Promise<void> = Promise.resolve();
/** Call with the refreshed job so its signed file URL is still valid. */
export function savePreparedFile(job: DownloadJob, options: SaveOptions = currentOptions): Promise<void> {
  const next = saveTail.catch(() => {}).then(() => saveFile(job, { ...options }));
  saveTail = next;
  return next;
}

async function saveFile(job: DownloadJob, options: SaveOptions): Promise<void> {
  if (!job.file_url) throw new Error('O arquivo expirou. Prepare-o novamente.');
  const suggested = preparedFileName(job, options.pattern);
  if (!options.directory) {
    const anchor = document.createElement('a');
    anchor.href = job.file_url; anchor.download = suggested; anchor.rel = 'noopener';
    document.body.appendChild(anchor); anchor.click(); anchor.remove();
    return;
  }
  const directory = options.directory;
  const permission = await directory.queryPermission({ mode: 'readwrite' });
  if (permission !== 'granted' && await directory.requestPermission({ mode: 'readwrite' }) !== 'granted') throw new Error('Autorize a gravação na pasta escolhida ou use Downloads do navegador.');
  let name = suggested;
  if (await exists(directory, name)) {
    if (options.collision === 'confirm') {
      if (!window.confirm(`Já existe ${name} nesta pasta. Substituir esse arquivo?`)) return;
    } else {
      const stem = suggested.slice(0, -(job.format.length + 1));
      let number = 2;
      while (await exists(directory, name)) name = `${stem} (${number++}).${job.format}`;
    }
  }
  const response = await fetch(job.file_url, { credentials: new URL(job.file_url, location.href).origin === location.origin ? 'same-origin' : 'omit' });
  if (!response.ok || !response.body) throw new Error('Não foi possível obter o arquivo. Atualize a lista e tente novamente.');
  const target = await directory.getFileHandle(name, { create: true });
  const writable = await target.createWritable();
  const reader = response.body.getReader();
  try {
    while (true) { const chunk = await reader.read(); if (chunk.done) break; await writable.write(chunk.value); }
    await writable.close();
  } catch (error) { await reader.cancel().catch(() => {}); await writable.abort().catch(() => {}); throw error; }
  finally { reader.releaseLock(); }
}

export function DownloadSaveOptions() {
  const [options, setOptions] = useState<SaveOptions>(currentOptions);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const picker = (window as unknown as { showDirectoryPicker?: (options: { mode: 'readwrite' }) => Promise<DirectoryHandle> }).showDirectoryPicker;
  const update = (changes: Partial<SaveOptions>) => {
    const next = { ...currentOptions, ...changes }; currentOptions = next; setOptions(next);
    try { localStorage.setItem(storageKey, JSON.stringify({ pattern: next.pattern, collision: next.collision })); } catch { /* Optional preference persistence. */ }
  };
  const choose = async () => {
    if (!picker) return;
    setBusy(true); setError('');
    try { update({ directory: await picker.call(window, { mode: 'readwrite' }) }); }
    catch (e) { if (!(e instanceof DOMException && e.name === 'AbortError')) setError('Não foi possível abrir a pasta. Use Downloads do navegador ou tente novamente.'); }
    finally { setBusy(false); }
  };
  const example = preparedFileName({ title: 'Dobrado Allah — Estevam Moura — Sociedade Filarmônica 25 de Março', video_id: 'exemplo', format: 'mp3' } as DownloadJob, options.pattern);
  return <section className="workspace-panel download-controls">
    <div><h2>Onde salvar os arquivos</h2><p>A pasta escolhida vale enquanto esta página estiver aberta.</p></div>
    <div className="download-toggle"><button aria-pressed={!options.directory} onClick={() => update({ directory: undefined })}>Downloads do navegador</button>{picker && <button disabled={busy} aria-pressed={!!options.directory} onClick={choose}><FolderOpen size={16}/> {options.directory ? `Pasta: ${options.directory.name}` : 'Escolher pasta'}</button>}</div>
    {!picker && <small>Este navegador usa sua configuração de downloads. Para escolher uma pasta nesta tela, use Chrome ou Edge.</small>}
    <label className="download-label">Nome dos arquivos<select value={['{titulo}', '{obra} — {compositor}', '{filarmonica} — {obra}', '{id} — {titulo}'].includes(options.pattern) ? options.pattern : 'custom'} onChange={e => e.target.value !== 'custom' && update({ pattern: e.target.value })}><option value="{titulo}">Título completo</option><option value="{obra} — {compositor}">Obra e compositor</option><option value="{filarmonica} — {obra}">Filarmônica e obra</option><option value="{id} — {titulo}">Identificador e título</option><option value="custom">Personalizado</option></select></label>
    <label className="download-label">Padrão editável<input value={options.pattern} onChange={e => update({ pattern: e.target.value })}/><small>Use {'{titulo}'}, {'{id}'}, {'{obra}'}, {'{compositor}'} e {'{filarmonica}'}. Obra, compositor e filarmônica são identificados somente nos títulos com a estrutura conhecida.</small></label>
    <small>Exemplo: {example}</small>
    {options.directory ? <label className="download-label">Se o arquivo já existir<select value={options.collision} onChange={e => update({ collision: e.target.value as SaveOptions['collision'] })}><option value="number">Criar outra cópia numerada</option><option value="confirm">Perguntar antes de substituir</option></select></label> : <small>A pasta e a resolução de nomes repetidos seguem as configurações do navegador. Servidores externos podem manter o nome original; escolha uma pasta acima para aplicar o padrão exatamente.</small>}
    {error && <div className="error-note" role="alert">{error}</div>}
  </section>;
}
