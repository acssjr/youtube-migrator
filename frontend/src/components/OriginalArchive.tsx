import { formatStoredDate } from '../services/dates';
import { useEffect, useRef, useState } from 'react';
import { acervoApi, AcervoRecord } from '../services/acervoApi';
import { copyBlob, hashBlob, manifestChunks, safeRelativePath } from '../services/originalArchive.mjs';

interface Entry { path: string; size: number; lastModified: number; sha256?: string; videoId: string }
interface Manifest { name: string; batch: string; files: Entry[]; destination?: string; created: string }
interface Selection extends Entry { file: File }
const readable = (size: number) => `${(size / 1024 / 1024).toFixed(1)} MB`;
export function OriginalArchive() {
  const [files, setFiles] = useState<Selection[]>([]);
  const [records, setRecords] = useState<AcervoRecord<Manifest>[]>([]);
  const [name, setName] = useState('Originais do acervo');
  const [checksums, setChecksums] = useState(true);
  const [overwrite, setOverwrite] = useState(false);
  const [destination, setDestination] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [page, setPage] = useState(0);
  const [savedPages, setSavedPages] = useState<Record<string, number>>({});
  const abort = useRef<AbortController>();
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; void load(); return () => { mounted.current = false; abort.current?.abort(); }; }, []);
  async function load() { try { const all = await acervoApi.records<Manifest>('original'); if (mounted.current) setRecords(all); } catch (e) { if (mounted.current) setMessage(String(e)); } }
  function select(list: FileList | null) {
    if (!list) return;
    const entries = Array.from(list).map(file => ({ file, path: file.webkitRelativePath || file.name, size: file.size, lastModified: file.lastModified, videoId: '' }));
    const seen = new Set<string>();
    try { entries.forEach(entry => { safeRelativePath(entry.path); if (seen.has(entry.path)) throw new Error('Há nomes repetidos. Selecione uma pasta para preservar os caminhos.'); seen.add(entry.path); }); setFiles(entries); setPage(0); setMessage(`${entries.length} arquivos selecionados. Os vídeos permanecem no seu computador.`); } catch (e) { setMessage(String(e)); }
  }
  async function chooseDestination() { try { setDestination(await (window as any).showDirectoryPicker({ mode: 'readwrite' })); } catch (e) { if ((e as DOMException).name !== 'AbortError') setMessage(String(e)); } }
  async function updateBinding(record: AcervoRecord<Manifest>, index: number, value: string) {
    const videoId = value.trim();
    if (videoId && !/^[A-Za-z0-9_-]{11}$/.test(videoId)) { setMessage('Informe um ID do YouTube válido, com 11 caracteres.'); return; }
    if (record.payload.files[index].videoId === videoId) return;
    const next = [...record.payload.files]; next[index] = { ...next[index], videoId };
    try { const updated = await acervoApi.update(record.id, { ...record.payload, files: next }, record.updated_at); setRecords(previous => previous.map(item => item.id === record.id ? updated : item)); setMessage('Vínculo do original atualizado.'); } catch (e) { setMessage(String(e)); await load(); }
  }
  async function run(copy: boolean) {
    if (!files.length || (copy && !destination)) return;
    const controller = new AbortController(); abort.current = controller; setBusy(true);
    const entries: Entry[] = []; let copied = 0; let unchanged = 0; let protectedFiles = 0;
    try {
      for (let index = 0; index < files.length; index++) {
        controller.signal.throwIfAborted(); const source = files[index];
        setMessage(`${index + 1}/${files.length}: ${source.path}`);
        const entry: Entry = { path: source.path, size: source.size, lastModified: source.lastModified, videoId: source.videoId.trim() };
        if (entry.videoId && !/^[A-Za-z0-9_-]{11}$/.test(entry.videoId)) throw new Error(`ID do YouTube inválido: ${source.path}`);
        if (checksums || copy) entry.sha256 = await hashBlob(source.file, controller.signal, bytes => setMessage(`Conferindo ${source.path}: ${readable(bytes)} / ${readable(source.size)}`));
        if (copy) {
          const parts = safeRelativePath(source.path); let dir = destination;
          for (const part of parts.slice(0, -1)) dir = await dir.getDirectoryHandle(part, { create: true });
          const basename = parts[parts.length - 1]; let target: any; let existing: File | undefined;
          try { target = await dir.getFileHandle(basename); existing = await target.getFile(); } catch (e) { if ((e as DOMException).name !== 'NotFoundError') throw e; }
          if (existing && existing.size === source.size && await hashBlob(existing, controller.signal) === entry.sha256) { unchanged++; }
          else if (existing && !overwrite) { protectedFiles++; }
          else { target = target || await dir.getFileHandle(basename, { create: true }); await copyBlob(source.file, target, controller.signal, bytes => setMessage(`Copiando ${source.path}: ${readable(bytes)} / ${readable(source.size)}`)); copied++; }
        }
        entries.push(entry);
      }
      const metadata = { name: name.trim() || 'Originais do acervo', batch: crypto.randomUUID(), created: new Date().toISOString(), ...(copy ? { destination: destination.name } : {}) };
      for (const payload of manifestChunks(entries, metadata)) { controller.signal.throwIfAborted(); await acervoApi.create('original', payload); }
      if (copy) await acervoApi.create('backup', { ...metadata, copied, unchanged, protectedFiles, filesCount: entries.length });
      await load(); setMessage(copy ? `Backup concluído: ${copied} copiados, ${unchanged} idênticos, ${protectedFiles} diferentes preservados. ${protectedFiles ? 'Marque a substituição para atualizar esses arquivos.' : ''}` : `${entries.length} originais registrados. Apenas o inventário foi salvo na nuvem.`);
    } catch (e) { setMessage(controller.signal.aborted ? 'Operação cancelada. Arquivos já concluídos permanecem na pasta. Nenhum original foi alterado.' : `Não foi possível concluir: ${String(e)}`); }
    finally { if (mounted.current) setBusy(false); }
  }
  const visible = files.slice(page * 30, page * 30 + 30);
  return <section className="workspace-panel">
    <h2>Originais e backup incremental</h2>
    <p>Registre onde estão seus arquivos, vincule cada original ao vídeo publicado e copie para outra pasta apenas os arquivos diferentes. O inventário fica na nuvem; o conteúdo dos vídeos é copiado no seu computador.</p>
    <div className="acervo-form"><label>Nome do conjunto<input value={name} onChange={e => setName(e.target.value)} disabled={busy} /></label></div>
    <div className="acervo-actions"><label>Selecionar arquivos<input type="file" multiple disabled={busy} onChange={e => select(e.target.files)} /></label><label>Selecionar pasta<input type="file" multiple ref={element => element?.setAttribute('webkitdirectory', '')} disabled={busy} onChange={e => select(e.target.files)} /></label></div>
    <label><input type="checkbox" checked={checksums} onChange={e => setChecksums(e.target.checked)} disabled={busy} /> Registrar SHA-256 para verificar a integridade</label>
    <p>{files.length} arquivos · {readable(files.reduce((sum, file) => sum + file.size, 0))}</p>
    <div className="acervo-record-list">{visible.map((file, offset) => <div className="acervo-record" key={file.path}><strong style={{ overflowWrap: 'anywhere' }}>{file.path}</strong><small> · {readable(file.size)}</small><label>ID do vídeo no YouTube (opcional)<input value={file.videoId} maxLength={11} placeholder="Ex.: dQw4w9WgXcQ" disabled={busy} onChange={e => { const next = [...files]; next[page * 30 + offset] = { ...file, videoId: e.target.value }; setFiles(next); }} /></label></div>)}</div>
    {files.length > 30 && <div className="acervo-actions"><button disabled={page === 0 || busy} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page + 1} de {Math.ceil(files.length / 30)}</span><button disabled={(page + 1) * 30 >= files.length || busy} onClick={() => setPage(page + 1)}>Próxima</button></div>}
    <div className="acervo-actions"><button onClick={() => run(false)} disabled={busy || !files.length}>Salvar inventário</button>{typeof (window as any).showDirectoryPicker === 'function' && <button disabled={busy} onClick={chooseDestination}>Escolher pasta do backup</button>}</div>
    {typeof (window as any).showDirectoryPicker !== 'function' && <p>Para copiar diretamente entre pastas, abra esta ferramenta no Chrome ou Edge. O inventário funciona neste navegador.</p>}
    {destination && <fieldset><legend>Destino: {destination.name}</legend><label><input type="checkbox" checked={overwrite} onChange={e => setOverwrite(e.target.checked)} disabled={busy} /> Autorizo substituir arquivos diferentes com o mesmo caminho no destino</label><p>Arquivos idênticos serão mantidos. A conferência compara o conteúdo por SHA-256. A estrutura de pastas da seleção será preservada.</p><button onClick={() => run(true)} disabled={busy || !files.length}>Conferir e copiar backup</button></fieldset>}
    {busy && <button onClick={() => abort.current?.abort()}>Cancelar operação</button>}<p role="status" aria-live="polite">{message}</p>
    <details><summary>Inventários salvos ({records.length})</summary>{records.map(record => {
      const savedPage = savedPages[record.id] || 0; const entries = record.payload.files || [];
      return <div className="acervo-record" key={record.id}><strong>{record.payload.name}</strong><p>{entries.length} arquivos · {formatStoredDate(record.created_at)}{record.payload.destination ? ` · Backup: ${record.payload.destination}` : ''}</p><button onClick={() => { const blob = new Blob([JSON.stringify(record.payload, null, 2)], { type: 'application/json' }); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = `inventario-${record.id}.json`; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }}>Baixar inventário</button><details><summary>Arquivos e vínculos ao YouTube</summary>{entries.slice(savedPage * 30, savedPage * 30 + 30).map((entry, offset) => <label key={`${entry.path}-${record.updated_at}`}><span style={{ overflowWrap: 'anywhere' }}>{entry.path} · {readable(entry.size)}{entry.sha256 ? ' · Integridade registrada' : ''}</span><input defaultValue={entry.videoId} maxLength={11} placeholder="ID do vídeo no YouTube (opcional)" disabled={busy} onBlur={e => updateBinding(record, savedPage * 30 + offset, e.target.value)} /></label>)}{entries.length > 30 && <div className="acervo-actions"><button disabled={savedPage === 0} onClick={() => setSavedPages(previous => ({ ...previous, [record.id]: savedPage - 1 }))}>Anterior</button><span>{savedPage + 1}/{Math.ceil(entries.length / 30)}</span><button disabled={(savedPage + 1) * 30 >= entries.length} onClick={() => setSavedPages(previous => ({ ...previous, [record.id]: savedPage + 1 }))}>Próxima</button></div>}</details></div>;
    })}</details>
  </section>;
}
