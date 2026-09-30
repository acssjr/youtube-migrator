import { useEffect, useState } from 'react';
import { api } from '../services/api';
import './AcervoForms.css';

type Criteria = { work: string; composer: string; arranger: string; ensemble: string; genre: string };
type Video = { id: string; title: string; published_at: string };
type Playlist = { id: string; title: string };
type Result = { id: string; title: string; url: string; complete: boolean; items: { video_id: string; status: string; message?: string }[] };
const empty: Criteria = { work: '', composer: '', arranger: '', ensemble: '', genre: '' };
const labels: Record<keyof Criteria, string> = { work: 'Obra', composer: 'Compositor', arranger: 'Arranjador', ensemble: 'Filarmônica', genre: 'Gênero' };
async function call<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`/api/smart-playlists/${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível concluir a operação.');
  return data;
}

export default function SmartPlaylists({ channelId }: { channelId?: string }) {
  const [accounts, setAccounts] = useState<{ channel_id: string; channel_title: string }[]>([]);
  const [channel, setChannel] = useState(channelId || '');
  const [criteria, setCriteria] = useState<Criteria>(empty);
  const [reviewedCriteria, setReviewedCriteria] = useState<Criteria>();
  const [videos, setVideos] = useState<Video[]>([]);
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [playlistId, setPlaylistId] = useState('');
  const [title, setTitle] = useState('');
  const [privacy, setPrivacy] = useState('private');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<Result>();
  useEffect(() => { if (channelId === undefined) api.auth.getAccounts().then(list => { setAccounts(list); setChannel(list[0]?.channel_id || ''); }).catch(e => setError(String(e))); }, [channelId]);
  useEffect(() => { if (channelId !== undefined) { setChannel(channelId); setReviewedCriteria(undefined); setVideos([]); setSelected([]); setResult(undefined); setPlaylistId(''); setPlaylists([]); } }, [channelId]);
  const invalidate = () => { setReviewedCriteria(undefined); setVideos([]); setSelected([]); setResult(undefined); setPlaylistId(''); setPlaylists([]); };
  const run = async (action: () => Promise<void>) => { setBusy(true); setError(''); try { await action(); } catch (e) { setError(String(e)); } finally { setBusy(false); } };
  const preview = () => run(async () => {
    const data = await call<{ videos: Video[]; playlists: Playlist[] }>('preview', { channel_id: channel, criteria });
    setVideos(data.videos); setPlaylists(data.playlists); setSelected(data.videos.map(v => v.id)); setReviewedCriteria({ ...criteria }); setResult(undefined); setPlaylistId('');
  });
  const publish = () => run(async () => {
    const data = await call<Result>('publish', { channel_id: channel, criteria: reviewedCriteria, title: playlistId ? playlists.find(p => p.id === playlistId)?.title || title : title, playlist_id: playlistId || null, privacy, video_ids: selected });
    setResult(data); setPlaylistId(data.id);
    setPlaylists(current => current.some(p => p.id === data.id) ? current : [...current, { id: data.id, title: data.title }]);
    setSelected(data.items.filter(item => item.status === 'error').map(item => item.video_id));
  });
  return <section className="workspace-panel acervo-tools">
    <div><h2>Playlists por critérios</h2><p>Combine os filtros, confira os vídeos e escolha quais adicionar. Os nomes de obra e autor devem corresponder aos créditos publicados; diferenças de acentos são aceitas.</p></div>
    <div className="acervo-form">
      {channelId === undefined && <label className="full">Canal<select disabled={busy} value={channel} onChange={e => { setChannel(e.target.value); invalidate(); }}>{accounts.map(a => <option key={a.channel_id} value={a.channel_id}>{a.channel_title}</option>)}</select></label>}
      {(Object.keys(labels) as (keyof Criteria)[]).map(key => <label key={key}>{labels[key]} <small>opcional</small><input disabled={busy} value={criteria[key]} onChange={e => { setCriteria({ ...criteria, [key]: e.target.value }); invalidate(); }} /></label>)}
    </div>
    <div className="acervo-actions"><button disabled={busy || !channel} onClick={preview}>{busy ? 'Aguarde…' : 'Buscar e conferir vídeos'}</button></div>
    {error && <p role="alert">{error}</p>}
    {reviewedCriteria && <>
      <div className="acervo-actions"><strong>{selected.length} de {videos.length} vídeos selecionados</strong><button disabled={busy} onClick={() => setSelected(videos.map(v => v.id))}>Selecionar todos</button><button disabled={busy} onClick={() => setSelected([])}>Limpar seleção</button></div>
      {!videos.length && <p>Nenhum vídeo corresponde a estes critérios. Ajuste os nomes e consulte novamente.</p>}
      <div className="acervo-record-list" style={{ maxHeight: 360, overflow: 'auto' }}>{videos.map(video => <label className="acervo-record" key={video.id} style={{ display: 'flex', gap: 12, alignItems: 'start' }}><input type="checkbox" disabled={busy} checked={selected.includes(video.id)} onChange={e => setSelected(current => e.target.checked ? [...current, video.id] : current.filter(id => id !== video.id))} /><span>{video.title}<br /><a href={`https://www.youtube.com/watch?v=${video.id}`} target="_blank" rel="noreferrer">Ver vídeo</a></span></label>)}</div>
      <div className="acervo-form">
        <label className="full">Destino<select disabled={busy} value={playlistId} onChange={e => { setPlaylistId(e.target.value); setResult(undefined); }}><option value="">Criar uma nova playlist</option>{playlists.map(p => <option key={p.id} value={p.id}>{p.title}</option>)}</select></label>
        {!playlistId && <><label>Título da playlist<input maxLength={150} disabled={busy} value={title} onChange={e => setTitle(e.target.value)} /></label><label>Visibilidade<select disabled={busy} value={privacy} onChange={e => setPrivacy(e.target.value)}><option value="private">Privada</option><option value="unlisted">Não listada</option><option value="public">Pública</option></select></label></>}
      </div>
      <p>A ordem segue a lista acima. Vídeos já presentes na playlist serão mantidos sem duplicação.</p>
      <div className="acervo-actions"><button disabled={busy || !selected.length || (!playlistId && !title.trim())} onClick={publish}>{result && !result.complete ? 'Tentar novamente os vídeos que falharam' : playlistId ? `Adicionar ${selected.length} vídeos à playlist` : `Criar playlist com ${selected.length} vídeos`}</button></div>
      {result && <div role="status"><p>{result.complete ? 'Todos os vídeos selecionados estão na playlist.' : 'Alguns vídeos falharam. Eles continuam selecionados para uma nova tentativa.'} <a href={result.url} target="_blank" rel="noreferrer">Abrir playlist</a></p>{result.items.filter(i => i.status === 'error').map(item => <p key={item.video_id}>{videos.find(v => v.id === item.video_id)?.title}: {item.message}</p>)}</div>}
    </>}
  </section>;
}
