import { useEffect, useRef, useState } from 'react';

type Item = { item_id: string; video_id: string | null; position: number; title: string; unavailable: boolean; privacy: string; duplicate: boolean };
type Playlist = { id: string; title: string; items: Item[]; empty: boolean; duplicate_title: boolean; duplicate_count: number; unavailable_count: number; private_count: number; missing_expected: string[] };
type Audit = { playlists: Playlist[]; unassigned: { id: string; title: string }[]; video_count: number };

export function PlaylistAudit({ channelId }: { channelId: string }) {
  const [report, setReport] = useState<Audit>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const currentChannel = useRef(channelId);
  currentChannel.current = channelId;
  useEffect(() => { setReport(undefined); setError(''); }, [channelId]);
  const run = async () => {
    setBusy(true); setError(''); setReport(undefined);
    try {
      const response = await fetch(`/api/playlist-audit/${encodeURIComponent(channelId)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Não foi possível consultar as playlists.');
      if (currentChannel.current === channelId) setReport(data);
    } catch (e) { if (currentChannel.current === channelId) setError(String(e)); } finally { setBusy(false); }
  };
  return <section className="workspace-panel acervo-tools">
    <h2>Conferir playlists</h2>
    <p>Confira repetições, vídeos indisponíveis, playlists vazias e apresentações incompletas. Esta consulta não altera o YouTube.</p>
    <button className="btn-primary" disabled={!channelId || busy} onClick={run}>{busy ? 'Conferindo todas as playlists…' : 'Conferir playlists do canal'}</button>
    {error && <p role="alert">{error}</p>}
    {report && <>
      <p role="status">{report.playlists.length} playlists conferidas · {report.video_count} vídeos no canal · {report.unassigned.length} fora das playlists.</p>
      <p>“Indisponível” significa que a API não retornou o vídeo; pode estar removido ou inacessível. Vídeos privados acessíveis aparecem separadamente.</p>
      {report.playlists.map(p => <details key={p.id} className="acervo-record">
        <summary>{p.title} — {p.items.length} itens{p.empty && ' · Vazia'}{p.duplicate_title && ' · Título repetido'}{p.duplicate_count > 0 && ` · ${p.duplicate_count} repetições`}{p.unavailable_count > 0 && ` · ${p.unavailable_count} indisponíveis`}{p.private_count > 0 && ` · ${p.private_count} privados`}{p.missing_expected.length > 0 && ` · ${p.missing_expected.length} vídeos esperados ausentes`}</summary>
        <p><a href={`https://www.youtube.com/playlist?list=${p.id}`} target="_blank" rel="noreferrer">Abrir playlist no YouTube</a></p>
        <ol>{p.items.map(i => <li key={i.item_id} value={i.position + 1}>{i.video_id ? <a href={`https://www.youtube.com/watch?v=${i.video_id}`} target="_blank" rel="noreferrer">{i.title}</a> : i.title}{i.duplicate && ' · Repetido'}{i.unavailable && ' · Indisponível'}{i.privacy === 'private' && ' · Privado'}</li>)}</ol>
        {p.missing_expected.length > 0 && <p>IDs esperados no cadastro da apresentação, mas ausentes: {p.missing_expected.join(', ')}</p>}
      </details>)}
      <details><summary>Vídeos do canal fora das playlists ({report.unassigned.length})</summary><ul>{report.unassigned.map(v => <li key={v.id}><a href={`https://www.youtube.com/watch?v=${v.id}`} target="_blank" rel="noreferrer">{v.title}</a></li>)}</ul></details>
    </>}
  </section>;
}
