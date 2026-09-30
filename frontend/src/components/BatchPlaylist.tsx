import { useEffect, useState } from 'react';
import { ExternalLink, ListPlus, Loader2 } from 'lucide-react';
import { api } from '../services/api';
import { Privacy } from '../services/uploadQueue';

interface Props { channelId: string; videos: { id: string; title: string }[]; ensemble: string }
interface Playlist { id: string; title: string; privacy: Privacy }
export function BatchPlaylist({ channelId, videos, ensemble }: Props) {
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [referenceId, setReferenceId] = useState('');
  const [title, setTitle] = useState('');
  const [privacy, setPrivacy] = useState<Privacy>('public');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [channelVideos, setChannelVideos] = useState<{ id: string; title: string }[]>();
  const selectedVideos = channelVideos || videos;
  useEffect(() => { setChannelVideos(undefined); setResult(undefined); }, [channelId, ensemble]);
  const [result, setResult] = useState<{ url: string; complete: boolean }>();
  useEffect(() => {
    let current = true;
    api.uploads.playlists(channelId).then(data => {
      if (!current) return;
      setPlaylists(data);
      const reference = data.find(item => /retreta.*5\s*[ªaºo]?\s*noite/i.test(item.title));
      if (reference) setReferenceId(reference.id);
    }).catch(e => { if (current) setError(String(e)); });
    return () => { current = false; };
  }, [channelId]);
  useEffect(() => {
    const reference = playlists.find(item => item.id === referenceId);
    if (!reference) return;
    setTitle(ensemble ? reference.title.replace(/(?:Sociedade\s+)?Filarm[oô]nica\s+.*?(?=\s+[|–—-]\s+|$)/i, ensemble) : reference.title);
    setPrivacy(reference.privacy); setResult(undefined);
  }, [referenceId, ensemble, playlists]);
  const create = async () => {
    setBusy(true); setError('');
    try {
      let complete = true;
      let url = '';
      const messages: string[] = [];
      for (let offset = 0; offset < selectedVideos.length; offset += 50) {
        const data = await api.uploads.createPlaylist(channelId, referenceId, title, selectedVideos.slice(offset, offset + 50).map(video => video.id), privacy);
        url = data.url; complete = complete && data.complete;
        messages.push(...data.items.filter(item => item.status === 'error').map(item => item.message || 'Não foi possível adicionar um vídeo.'));
      }
      setResult({ url, complete });
      if (!complete) setError(messages.join(' '));
    }
    catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  };
  const discover = async () => {
    setBusy(true); setError(''); setResult(undefined);
    try { setChannelVideos(await api.uploads.ensembleVideos(channelId, ensemble)); }
    catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  };
  return <section className="workspace-panel batch-playlist"><div className="panel-top"><div><h2>Playlist para este lote</h2><p>Use o nome de uma playlist existente como referência e reúna os vídeos enviados.</p></div><ListPlus size={23}/></div>
    <div className="upload-defaults"><label>Playlist de referência<select value={referenceId} disabled={busy} onChange={event => setReferenceId(event.target.value)}><option value="">Selecione a referência</option>{playlists.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label><label>Nome da nova playlist<input value={title} maxLength={150} disabled={busy} onChange={event => { setTitle(event.target.value); setResult(undefined); }}/></label><label>Visibilidade da playlist<select value={privacy} disabled={busy} onChange={event => setPrivacy(event.target.value as Privacy)}><option value="public">Pública</option><option value="unlisted">Não listada</option><option value="private">Privada</option></select></label></div>
    <div className="panel-footer"><span>Filarmônica: {ensemble}</span><button className="secondary-action" disabled={busy || !ensemble} onClick={discover}>Buscar todos os vídeos da filarmônica no canal</button></div>
    <ul>{selectedVideos.map(video => <li key={video.id}>{video.title}</li>)}</ul>
    {error && <p role="alert" className="error-note">{error}</p>}
    <div className="panel-footer"><span>{selectedVideos.length} vídeo(s) {channelVideos ? 'encontrados no canal para esta filarmônica' : 'enviados neste lote'}. Se esse título já existir, a playlist será reaproveitada, sem duplicar vídeos.</span><button className="primary-action" disabled={busy || !selectedVideos.length || !referenceId || !title.trim()} onClick={create}>{busy ? <Loader2 className="spin" size={17}/> : <ListPlus size={17}/>} {result?.complete ? 'Conferir novamente' : 'Criar playlist e adicionar vídeos'}</button></div>
    {result && <div className="playlist-result" role="status"><strong>{result.complete ? 'Todos os vídeos estão na playlist.' : 'Alguns vídeos não foram adicionados. Tente novamente.'}</strong><a href={result.url} target="_blank" rel="noreferrer">Abrir playlist no YouTube <ExternalLink size={14}/></a></div>}
  </section>;
}
