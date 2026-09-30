import { useEffect, useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { DownloadJob } from '../types';

interface Props { jobs: DownloadJob[]; mode: string }

export function DownloadPackages({ jobs, mode }: Props) {
  const [selected, setSelected] = useState<string[]>([]);
  const [title, setTitle] = useState('Meu acervo');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [result, setResult] = useState<{ url: string; included: number; missing: number }>();
  const available = jobs.filter(job => ['completed', 'error', 'expired'].includes(job.status));
  useEffect(() => { setSelected(previous => previous.filter(id => jobs.some(job => job.id === id))); }, [jobs]);
  if (!available.length) return null;
  if (mode === 'companion') return <div className="notice">Para salvar os arquivos juntos em um pacote, abra os downloads no aplicativo local.</div>;
  const toggle = (id: string) => { setSelected(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id]); setResult(undefined); };
  const readyMp3 = jobs.filter(job => job.format === 'mp3' && job.status === 'completed' && job.file_url);
  const create = async (ids = selected, automaticSave = false) => {
    setBusy(true); setError(''); setNotice(''); setResult(undefined);
    try {
      const response = await fetch('/api/download-packages', { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ job_ids: ids, title }) });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível preparar o pacote.');
      if (automaticSave && data.included > 0) {
        const link = document.createElement('a'); link.href = data.url; link.download = '';
        document.body.appendChild(link); link.click(); link.remove();
      }
      if (automaticSave && data.included > 0) setNotice(`Download do ZIP iniciado com ${data.included} MP3(s).${data.missing ? ` ${data.missing} item(ns) indisponíveis estão no relatório.` : ''}`);
      else setResult(data);
    } catch (e) { setError(e instanceof Error ? e.message : 'Não foi possível preparar o pacote.'); }
    finally { setBusy(false); }
  };
  return <section className="workspace-panel download-form">
    <div className="panel-top"><div><h2>Levar tudo em um pacote</h2><p>Um ZIP com arquivos numerados, lista de faixas e relatório dos itens que falharam. Os vídeos não serão baixados novamente.</p></div></div>
    <div className="download-controls">
      {!!readyMp3.length && <button className="primary-action" disabled={busy} onClick={() => create(readyMp3.map(job => job.id), true)}><Download size={18}/>{busy ? 'Preparando ZIP…' : `Baixar todos os MP3s prontos (${readyMp3.length})`}</button>}
      <small>Inclui os MP3s já convertidos que ainda estão disponíveis, mesmo que você já tenha salvo antes.</small>
      <label className="download-label">Nome do pacote<input value={title} maxLength={120} disabled={busy} onChange={e => { setTitle(e.target.value); setResult(undefined); }}/></label>
      <div className="download-toggle"><button disabled={busy} onClick={() => { setSelected(available.map(job => job.id)); setResult(undefined); }}>Selecionar todos na ordem da lista</button><button disabled={busy} onClick={() => { setSelected([]); setResult(undefined); }}>Limpar seleção</button></div>
      <p>A numeração segue a ordem em que você selecionar. Inclua itens que falharam para registrá-los no relatório.</p>
      <div style={{ maxHeight: 320, overflowY: 'auto' }}>{available.map(job => <label key={job.id} style={{ display: 'flex', gap: 10, padding: '8px 0', alignItems: 'center' }}>
        <input type="checkbox" checked={selected.includes(job.id)} disabled={busy} onChange={() => toggle(job.id)}/>
        <span>{selected.includes(job.id) ? `${selected.indexOf(job.id) + 1}. ` : ''}{job.title} <small>({job.format.toUpperCase()} · {job.status === 'completed' ? 'Pronto' : 'Será registrado no relatório'})</small></span>
      </label>)}</div>
      <button className="primary-action" disabled={busy || !selected.length} onClick={() => create()}>{busy ? <Loader2 className="spin" size={18}/> : <Download size={18}/>} {busy ? 'Preparando pacote…' : `Preparar pacote (${selected.length})`}</button>
      {notice && <div className="notice" role="status">{notice}</div>}
      {error && <div className="error-note" role="alert">{error}</div>}
      {result && <div className="notice" role="status"><p>{result.included} arquivo(s) incluído(s). {result.missing > 0 ? `${result.missing} item(ns) registrado(s) no relatório de falhas.` : 'Todos os arquivos foram incluídos.'}</p><a href={result.url} className="primary-action" onClick={() => setTimeout(() => setResult(undefined), 1000)}>Salvar pacote ZIP</a><small>O pacote é removido após o envio. Você pode prepará-lo novamente enquanto os arquivos estiverem disponíveis.</small></div>}
    </div>
  </section>;
}
