import { useMemo, useRef, useState } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import { api } from '../services/api';
import { DownloadJob } from '../types';

interface Props { jobs: DownloadJob[]; mode: string; onChanged: () => void }
const identity = (job: DownloadJob) => `${job.video_id}:${job.format}:${job.resolution}`;

export function DownloadRetry({ jobs, mode, onChanged }: Props) {
  const [retried, setRetried] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const running = useRef(false);
  const failed = useMemo(() => {
    const active = new Set(jobs.filter(job => ['queued', 'running'].includes(job.status) || (job.status === 'completed' && !!job.file_url)).map(identity));
    const seen = new Set<string>();
    return jobs.filter(job => {
      const key = identity(job);
      if (job.status !== 'error' || retried.includes(job.id) || active.has(key) || seen.has(key)) return false;
      seen.add(key); return true;
    });
  }, [jobs, retried]);
  const retry = async () => {
    if (running.current || !failed.length) return;
    running.current = true; setBusy(true); setError(''); setMessage('');
    const groups = new Map<string, DownloadJob[]>();
    failed.forEach(job => {
      const key = `${job.format}:${job.resolution}`;
      groups.set(key, [...(groups.get(key) || []), job]);
    });
    let count = 0;
    try {
      for (const batch of groups.values()) {
        const queued = await api.downloads.create(batch.map(job => job.video_id), batch[0].format, batch[0].resolution);
        const accepted = new Set(queued.map(identity));
        const acceptedIds = batch.filter(job => accepted.has(identity(job))).map(job => job.id);
        setRetried(previous => [...previous, ...acceptedIds]);
        count += acceptedIds.length;
        onChanged();
        if (acceptedIds.length !== batch.length) throw new Error('Parte da seleção não entrou na fila. Atualize a lista antes de tentar novamente.');
      }
      setMessage(`${count} download(s) adicionado(s) novamente à fila, mantendo formato e resolução.`);
    } catch (failure) {
      setError(`${count ? `${count} download(s) já entrou(aram) na fila. ` : ''}${failure instanceof Error ? failure.message : 'Não foi possível tentar novamente.'}`);
      onChanged();
    } finally { running.current = false; setBusy(false); }
  };
  if (mode === 'companion' || (!failed.length && !message && !error)) return null;
  return <section className="workspace-panel download-form">
    <div className="panel-top"><div><h2>Tentar novamente os que falharam</h2><p>Repete apenas as falhas pendentes, com o mesmo formato e resolução. Os arquivos prontos são preservados.</p></div></div>
    <div className="download-controls">
      <button className="btn btn-secondary" disabled={busy || !failed.length} onClick={retry}>
        {busy ? <Loader2 className="spin" size={18}/> : <RefreshCw size={18}/>}
        {busy ? 'Adicionando à fila…' : `Tentar novamente (${failed.length})`}
      </button>
      {!!failed.length && <details><summary>Ver downloads que serão repetidos</summary><ul>{failed.map(job => <li key={job.id}>{job.title} · {job.format.toUpperCase()}{job.format === 'mp4' ? ` · ${job.resolution}p` : ''}</li>)}</ul></details>}
      {message && <div className="notice" role="status">{message}</div>}
      {error && <div className="error-note" role="alert">{error}</div>}
    </div>
  </section>;
}
