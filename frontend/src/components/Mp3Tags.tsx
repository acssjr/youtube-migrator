import { useState } from 'react';
import { DownloadJob } from '../types';

const fields = { title: 'Título', artist: 'Intérprete / filarmônica', composer: 'Compositor', album: 'Álbum / projeto', genre: 'Gênero', year: 'Ano da execução', track: 'Número da faixa', notes: 'Observações' };
type TagKey = keyof typeof fields;
interface Props { jobs: DownloadJob[]; mode: string; onChanged: () => void }

export function Mp3Tags({ jobs, mode, onChanged }: Props) {
  const [selection, setSelection] = useState<string[]>([]);
  const [values, setValues] = useState<Partial<Record<TagKey, string>>>({});
  const [enabled, setEnabled] = useState<TagKey[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const available = jobs.filter(job => job.format === 'mp3' && job.status === 'completed' && new Date(/[Zz]|[+-]\d\d:\d\d$/.test(job.expires_at) ? job.expires_at : job.expires_at + 'Z').getTime() > Date.now());
  if (!available.length || mode === 'companion') return null;
  const call = async (url: string, options?: RequestInit) => {
    const response = await fetch(url, { credentials: 'same-origin', ...options });
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Não foi possível salvar a identificação.');
    return result;
  };
  const read = async () => {
    setBusy(true); setMessage('');
    try { const result = await call(`/api/mp3-tags/${selection[0]}`); setValues(result.tags); setEnabled([]); setMessage('Identificação carregada. Marque os campos que deseja alterar.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Não foi possível ler o arquivo.'); }
    finally { setBusy(false); }
  };
  const fromTitle = () => {
    const job = available.find(item => item.id === selection[0]);
    if (!job) return;
    const parts = job.title.split(/\s+[—–]\s+/).map(part => part.trim()).filter(Boolean);
    const known = parts.length >= 3 && /filarm[oô]nica/i.test(parts[parts.length - 1]);
    const genre = /^(Dobrado|Marcha|Maxixe|Valsa|Bolero|Fantasia|Suíte|Hino|Polca|Samba|Choro|Frevo)\s+/i.exec(parts[0]);
    const draft: Partial<Record<TagKey,string>> = {title:known ? parts[0].replace(genre?.[0] || /$^/, '') : job.title};
    if (genre && known) draft.genre=genre[1];
    if (known) {draft.artist=parts[parts.length - 1];if (!/^Arr\./i.test(parts[1])) draft.composer=parts[1];}
    setValues(current => ({...current,...draft}));setEnabled(current => [...new Set([...current,...Object.keys(draft) as TagKey[]])]);setMessage('Campos extraídos do título. Confira os créditos antes de salvar.');
  };
  const save = async () => {
    setBusy(true); setMessage('');
    try {
      const result = await call('/api/mp3-tags', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ job_ids: selection.filter(id => available.some(job => job.id === id)), tags: Object.fromEntries(enabled.map(key => [key, values[key] || ''])) }) });
      const successes = result.results.filter((item: { applied: boolean }) => item.applied).length;
      setMessage(`${successes} arquivo(s) atualizado(s). ${result.results.length - successes} falha(s).`); onChanged();
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Não foi possível salvar.'); }
    finally { setBusy(false); }
  };
  return <details className="workspace-panel download-form"><summary style={{ padding: 20, cursor: 'pointer' }}>Identificação dos MP3</summary><div className="download-controls">
    <p>Salve compositor, filarmônica e projeto dentro dos arquivos. Apenas os campos marcados serão alterados; um campo marcado vazio remove seu valor. Isso não altera o YouTube.</p>
    <button disabled={busy} onClick={() => setSelection(available.map(job => job.id))}>Selecionar todos os MP3 prontos</button>
    <div style={{ maxHeight: 240, overflowY: 'auto' }}>{available.map(job => <label key={job.id} style={{ display: 'flex', gap: 10, padding: 8 }}><input type="checkbox" disabled={busy} checked={selection.includes(job.id)} onChange={() => setSelection(current => current.includes(job.id) ? current.filter(id => id !== job.id) : [...current, job.id])}/>{job.title}</label>)}</div>
    <button disabled={busy || selection.length !== 1} onClick={read}>Ler identificação do arquivo selecionado</button>
    <button className="secondary-action" disabled={busy || selection.length !== 1} onClick={fromTitle}>Sugerir identificação pelo título</button>
    <div className="acervo-form">{(Object.keys(fields) as TagKey[]).map(key => <label key={key} className="download-label"><span><input type="checkbox" disabled={busy} checked={enabled.includes(key)} onChange={() => setEnabled(current => current.includes(key) ? current.filter(item => item !== key) : [...current, key])}/> {fields[key]}</span><input disabled={busy || !enabled.includes(key)} value={values[key] || ''} onChange={e => setValues(current => ({ ...current, [key]: e.target.value }))} placeholder={key === 'year' ? 'Informe o ano, sem inferir pela publicação' : key === 'track' ? '1 ou 1/8' : ''}/></label>)}</div>
    <button className="primary-action" disabled={busy || !enabled.length || !selection.some(id => available.some(job => job.id === id))} onClick={save}>{busy ? 'Salvando…' : 'Salvar nos MP3 selecionados'}</button>
    {message && <p role="status">{message}</p>}
  </div></details>;
}
