import { useEffect, useState } from 'react';
import { ArrowDown, ArrowUp, Pause, Play, X } from 'lucide-react';
import type { DownloadJob } from '../types';

type State = { paused: boolean; job_ids: string[] };
type Props = { jobs: DownloadJob[]; mode: string; onChanged: () => void };

async function control<T>(path = '', body?: unknown): Promise<T> {
  const response = await fetch(`/api/download-controls${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível alterar a fila.');
  return data;
}

export function DownloadQueueControls({ jobs, mode, onChanged }: Props) {
  const [state, setState] = useState<State>({ paused: false, job_ids: [] });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const signature = jobs.map(job => `${job.id}:${job.status}`).join('|');
  useEffect(() => {
    if (mode === 'companion') return;
    let alive = true;
    control<State>().then(data => { if (alive) { setState(data); setLoaded(true); setError(''); } })
      .catch(reason => { if (alive) setError(reason instanceof Error ? reason.message : 'Falha ao carregar a fila.'); });
    return () => { alive = false; };
  }, [signature, mode]);

  async function change(path: string, body: unknown) {
    setBusy(true); setError('');
    try {
      await control(path, body);
      setState(await control<State>());
      onChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Não foi possível alterar a fila.');
      try { setState(await control<State>()); } catch { /* Preserve the actionable error. */ }
      onChanged();
    } finally { setBusy(false); }
  }

  const waiting = state.job_ids.map(id => jobs.find(job => job.id === id)).filter((job): job is DownloadJob => !!job);
  const running = jobs.filter(job => job.status === 'running');
  function move(index: number, delta: number) {
    const ids = [...state.job_ids];
    [ids[index], ids[index + delta]] = [ids[index + delta], ids[index]];
    void change('/reorder', { job_ids: ids });
  }
  if (mode === 'companion') return null;
  return <section className="workspace-panel download-controls" aria-label="Controles da fila">
    <div className="section-heading"><div><h2>Organizar a fila</h2>
      <p>{state.paused ? 'Fila pausada. Retome quando quiser.' : 'Os arquivos são preparados na ordem abaixo.'} A pausa segura os próximos arquivos; o download atual continua.</p>
    </div></div>
    {error && <p className="error-note" role="alert">{error}</p>}
    <button type="button" className="secondary-action" disabled={busy || !loaded}
      onClick={() => void change('/pause', { paused: !state.paused })}>
      {state.paused ? <Play size={16} /> : <Pause size={16} />}{state.paused ? 'Retomar fila' : 'Pausar fila'}
    </button>
    <ul style={{ listStyle: 'none', padding: 0 }}>
      {[...running, ...waiting].map(job => {
        const index = state.job_ids.indexOf(job.id);
        return <li key={job.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '12px 0', borderBottom: '1px solid var(--border, #e5e2dc)' }}>
          <span style={{ flex: 1, minWidth: 0, overflowWrap: 'anywhere' }}>{job.status === 'running' ? 'Em andamento · ' : `${index + 1} · `}{job.title}</span>
          {job.status === 'queued' && <>
            <button type="button" className="secondary-action" aria-label={`Mover ${job.title} para cima`} disabled={busy || index <= 0} onClick={() => move(index, -1)}><ArrowUp size={16} /></button>
            <button type="button" className="secondary-action" aria-label={`Mover ${job.title} para baixo`} disabled={busy || index < 0 || index >= state.job_ids.length - 1} onClick={() => move(index, 1)}><ArrowDown size={16} /></button>
          </>}
          <button type="button" className="secondary-action" disabled={busy} onClick={() => void change(`/jobs/${job.id}/cancel`, {})}><X size={16} />Cancelar</button>
        </li>;
      })}
    </ul>
    {!waiting.length && !running.length && <p>Nenhum download aguardando ou em andamento.</p>}
  </section>;
}
