import { useEffect, useState } from 'react';
import { api } from '../services/api';

type Snippet = { title: string; description: string };
type Revision = { id: string; video_id: string; before_snippet: Snippet; after_snippet: Snippet; status: string; created_at: string; restores_id?: string };
type Video = { id: string; title: string; description: string };

async function revisionsRequest<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/revisions${path}`, { method: body ? 'POST' : 'GET', headers: { 'Content-Type': 'application/json' }, ...(body ? { body: JSON.stringify(body) } : {}) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível concluir a operação.');
  return data;
}

function Comparison({ revision }: { revision: Revision }) {
  return <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(min(100%,260px),1fr))', gap: 16 }}>
    {(['before_snippet', 'after_snippet'] as const).map((key, index) => <div key={key}>
      <h4>{index ? 'Depois' : 'Antes'}</h4>
      <strong>{revision[key].title}</strong>
      <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', fontFamily: 'inherit', maxHeight: 400, overflow: 'auto', padding: 12, background: '#f6f5f1', borderRadius: 8 }}>{revision[key].description || '(Sem descrição)'}</pre>
    </div>)}
  </div>;
}

/** Standalone editor + audit history; channelId can follow the parent channel picker. */
export default function MetadataRevisions({ channelId: initialChannel }: { channelId?: string }) {
  const [accounts, setAccounts] = useState<{ channel_id: string; channel_title: string }[]>([]);
  const [channel, setChannel] = useState(initialChannel || '');
  const [videos, setVideos] = useState<Video[]>([]);
  const [history, setHistory] = useState<Revision[]>([]);
  const [videoId, setVideoId] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [preview, setPreview] = useState<Revision>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  useEffect(() => { if (initialChannel !== undefined) setChannel(initialChannel); }, [initialChannel]);
  useEffect(() => { if (initialChannel === undefined) api.auth.getAccounts().then(data => { setAccounts(data); setChannel(data[0]?.channel_id || ''); }).catch(e => setError(String(e))); }, [initialChannel]);
  useEffect(() => {
    if (!channel) return;
    let active = true;
    setPreview(undefined); setVideoId(''); setHistory([]); setVideos([]); setError('');
    Promise.all([revisionsRequest<Video[]>(`/${encodeURIComponent(channel)}/videos`), revisionsRequest<Revision[]>(`/${encodeURIComponent(channel)}`)]).then(([list, changes]) => { if (active) { setVideos(list); setHistory(changes); } }).catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, [channel]);
  const selectVideo = (id: string) => {
    setVideoId(id); setPreview(undefined); setMessage('');
    const video = videos.find(item => item.id === id);
    setTitle(video?.title || ''); setDescription(video?.description || '');
  };
  const refresh = async () => {
    const [list, changes] = await Promise.all([revisionsRequest<Video[]>(`/${encodeURIComponent(channel)}/videos`), revisionsRequest<Revision[]>(`/${encodeURIComponent(channel)}`)]);
    setVideos(list); setHistory(changes);
  };
  const run = async (operation: () => Promise<void>) => { setBusy(true); setError(''); setMessage(''); try { await operation(); } catch (e) { setError(String(e)); } finally { setBusy(false); } };
  const compare = () => run(async () => {
    const result = await revisionsRequest<Revision[]>('/preview', { channel_id: channel, items: [{ video_id: videoId, title, description }] });
    setPreview(result[0]);
  });
  const publish = () => run(async () => {
    if (!preview) return;
    const results = await revisionsRequest<{ status: string; message?: string }[]>('/apply', { channel_id: channel, revision_ids: [preview.id] });
    if (results[0]?.status !== 'applied') throw new Error(results[0]?.message || 'A publicação não foi confirmada.');
    setPreview(undefined); setMessage('Alteração publicada. A versão anterior foi guardada.'); await refresh();
  });
  const restore = (revision: Revision) => {
    if (!window.confirm('Restaurar o título e a descrição mostrados em “Antes”? Se o vídeo tiver mudado depois, a restauração será bloqueada.')) return;
    void run(async () => { await revisionsRequest(`/${encodeURIComponent(channel)}/${revision.id}/restore`, {}); setPreview(undefined); setMessage('Versão anterior restaurada.'); await refresh(); });
  };
  return <section className="workspace-panel">
    <h2>Comparar e restaurar alterações</h2>
    <p>O texto é publicado exatamente como você escreveu. As versões anteriores são guardadas a partir das alterações feitas por este aplicativo.</p>
    {initialChannel === undefined && <label>Canal<select value={channel} disabled={busy} onChange={e => setChannel(e.target.value)}><option value="">Selecione um canal</option>{accounts.map(item => <option key={item.channel_id} value={item.channel_id}>{item.channel_title}</option>)}</select></label>}
    {error && <p className="notice" role="alert">{error}</p>}
    {message && <p className="notice" role="status">{message}</p>}
    <label>Vídeo<select value={videoId} disabled={busy} onChange={e => selectVideo(e.target.value)}><option value="">Escolha o vídeo</option>{videos.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
    {videoId && <div style={{ display: 'grid', gap: 16, marginTop: 16 }}>
      <label>Título<input value={title} maxLength={100} disabled={busy} onChange={e => { setTitle(e.target.value); setPreview(undefined); }} /></label>
      <label>Descrição<textarea value={description} maxLength={5000} rows={12} style={{ width: '100%' }} disabled={busy} onChange={e => { setDescription(e.target.value); setPreview(undefined); }} /></label>
      <button className="secondary-action" disabled={busy || !title.trim()} onClick={compare}>{busy ? 'Aguarde…' : 'Comparar antes de publicar'}</button>
      {preview && <div><Comparison revision={preview}/><button className="primary-action" disabled={busy} onClick={publish}>Publicar esta alteração</button></div>}
    </div>}
    <h3>Últimas 200 revisões</h3>
    {!history.length && <p>Nenhuma revisão registrada neste canal.</p>}
    {history.filter(item => item.status !== 'preview').map(revision => <details key={revision.id} style={{ borderTop: '1px solid #e5e3dc', padding: '12px 0' }}>
      <summary>{revision.after_snippet.title} · {({ applied: 'Publicada', failed: 'Sem confirmação', pending: 'Em processamento', restored: 'Restaurada' } as Record<string, string>)[revision.status] || revision.status} · {new Date(`${revision.created_at}Z`).toLocaleString('pt-BR')}</summary>
      <Comparison revision={revision}/>
      {['applied', 'failed', 'pending'].includes(revision.status) && <button className="secondary-action" disabled={busy} onClick={() => restore(revision)}>Restaurar a versão anterior</button>}
    </details>)}
  </section>;
}
