import { Mp3Tags } from '../components/Mp3Tags';
import { DownloadSaveOptions, savePreparedFile } from '../components/DownloadSaveOptions';
import { DownloadRetry } from '../components/DownloadRetry';
import { DownloadPackages } from '../components/DownloadPackages';
import { DownloadQueueControls } from '../components/DownloadQueueControls';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Download, ExternalLink, Loader2, Music, RefreshCw, Video } from 'lucide-react';
import { api } from '../services/api';
import { Account, DownloadJob, DownloadStatus, EmptyVideo } from '../types';

const statuses = { cancelled: 'Cancelado', queued: 'Na fila', running: 'Baixando / convertendo', completed: 'Pronto', error: 'Falhou', expired: 'Expirado' };
const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'Não foi possível concluir a solicitação.';

export function DownloadsPage() {
  const [source, setSource] = useState<'links' | 'channel' | 'playlist'>('links');
  const [format, setFormat] = useState<'mp3' | 'mp4'>('mp3');
  const [resolution, setResolution] = useState(1080);
  const [links, setLinks] = useState('');
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [channelId, setChannelId] = useState('');
  const [videos, setVideos] = useState<EmptyVideo[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [playlists, setPlaylists] = useState<{ id: string; title: string }[]>([]);
  const [playlistInput, setPlaylistInput] = useState('');
  const [playlistInfo, setPlaylistInfo] = useState<{ title: string; unavailable_count: number; duplicate_count: number }>();
  const [playlistOptionsLoading, setPlaylistOptionsLoading] = useState(false);
  const playlistVersion = useRef(0);
  const [jobs, setJobs] = useState<DownloadJob[]>([]);
  const [status, setStatus] = useState<DownloadStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [channelError, setChannelError] = useState('');
  const [connectionError, setConnectionError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [transferReceived, setTransferReceived] = useState(false);
  const [localLink, setLocalLink] = useState('');
  const [launchLink, setLaunchLink] = useState('');
  const pendingTransfer = useRef<{ sources: string[]; format: 'mp3' | 'mp4'; resolution: number }>();
  const transferStarted = useRef(false);

  useEffect(() => { setLocalLink(''); }, [links, selected, source, channelId, playlistInput, format, resolution]);

  useEffect(() => {
    const receive = () => {
    const raw = new URLSearchParams(window.location.hash.slice(1)).get('transfer');
    if (!raw) return;
    try {
      if (!['127.0.0.1', 'localhost'].includes(window.location.hostname)) throw new Error('Abra a seleção no aplicativo local.');
      const transfer = JSON.parse(raw);
      if (!Array.isArray(transfer.sources) || !transfer.sources.length ||
          !transfer.sources.every((id: unknown) => typeof id === 'string' && /^[A-Za-z0-9_-]{11}$/.test(id)) ||
          !['mp3', 'mp4'].includes(transfer.format) || ![360, 720, 1080].includes(transfer.resolution)) throw new Error('A seleção recebida é inválida. Envie novamente pelo site.');
      setLinks(transfer.sources.map((id: string) => `https://www.youtube.com/watch?v=${id}`).join('\n'));
      setFormat(transfer.format); setResolution(transfer.resolution); setTransferReceived(true);
      transferStarted.current = false;
      pendingTransfer.current = transfer.autostart === true ? transfer : undefined;
      setRefresh(n => n + 1);
    } catch (e) { setError(errorMessage(e)); }
    window.history.replaceState({}, '', window.location.pathname + window.location.search);
    };
    receive();
    window.addEventListener('hashchange', receive);
    return () => window.removeEventListener('hashchange', receive);
  }, []);

  useEffect(() => {
    if (!pendingTransfer.current || transferStarted.current || status?.mode !== 'local' || !status.engine?.ffmpeg) return;
    transferStarted.current = true;
    const transfer = pendingTransfer.current;
    setBusy(true); setError('');
    api.downloads.create(transfer.sources, transfer.format, transfer.resolution).then(created => {
      setJobs(previous => [...created, ...previous.filter(item => !created.some(next => next.id === item.id))]);
      setNotice('Seleção recebida: a preparação começou automaticamente.');
      setLinks(''); setRefresh(n => n + 1);
    }).catch(e => setError(errorMessage(e))).finally(() => setBusy(false));
  }, [status]);

  useEffect(() => {
    let live = true;
    api.auth.getAccounts().then(data => {
      if (live) { setAccounts(data); setChannelId(data[0]?.channel_id || ''); }
    }).catch(() => { if (live) setChannelError('Não foi possível consultar os canais conectados. Confira Configurações.'); });
    return () => { live = false; };
  }, []);

  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        // Sequential on the first request so a new browser receives its ownership cookie first.
        const info = await api.downloads.status();
        const data = info.mode === 'companion' ? [] : await api.downloads.jobs();
        if (live) { setStatus(info); setJobs(data); setConnectionError(''); }
        if (info.mode === 'companion') return;
      } catch (e) {
        if (live) setConnectionError(errorMessage(e));
      }
      if (live) timer = setTimeout(poll, 3000);
    };
    poll();
    return () => { live = false; clearTimeout(timer); };
  }, [refresh]);

  useEffect(() => {
    let live = true;
    setVideos([]); setSelected([]); setQuery(''); setChannelError(''); setPlaylistInfo(undefined); playlistVersion.current += 1;
    setLoading(false);
    if (source !== 'channel' || !channelId) return;
    setLoading(true); setChannelError('');
    api.downloads.channel(channelId).then(data => { if (live) setVideos(data); })
      .catch(e => { if (live) setChannelError(errorMessage(e)); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [source, channelId]);

  useEffect(() => {
    let live = true;
    setPlaylists([]); setPlaylistOptionsLoading(false);
    if (source !== 'playlist' || !channelId) return;
    setPlaylistOptionsLoading(true);
    api.uploads.playlists(channelId).then(data => { if (live) setPlaylists(data); })
      .catch(e => { if (live) setChannelError(errorMessage(e)); })
      .finally(() => { if (live) setPlaylistOptionsLoading(false); });
    return () => { live = false; };
  }, [source, channelId]);

  const changePlaylist = (value: string) => {
    playlistVersion.current += 1;
    setPlaylistInput(value); setPlaylistInfo(undefined); setVideos([]); setSelected([]); setChannelError(''); setQuery('');
  };
  const loadPlaylist = async () => {
    const version = ++playlistVersion.current;
    setLoading(true); setChannelError(''); setVideos([]); setSelected([]); setPlaylistInfo(undefined);
    try {
      const data = await api.downloads.playlist(channelId, playlistInput.trim());
      if (version !== playlistVersion.current) return;
      setPlaylistInfo(data); setVideos(data.videos); setSelected(data.videos.map(video => video.id));
    } catch (e) { if (version === playlistVersion.current) setChannelError(errorMessage(e)); }
    finally { if (version === playlistVersion.current) setLoading(false); }
  };

  const sources = source === 'links' ? links.split(/\r?\n/).map(s => s.trim()).filter(Boolean) : videos.filter(video => selected.includes(video.id)).map(video => video.id);
  const visible = useMemo(() => videos.filter(v => v.title.toLocaleLowerCase().includes(query.toLocaleLowerCase())), [videos, query]);
  const submit = async () => {
    setBusy(true); setError('');
    try {
      if (status?.mode === 'companion') {
        const transfer = await api.downloads.handoff(sources, format, resolution, source === 'channel' ? channelId : undefined);
        setLocalLink(transfer.url);
        setLaunchLink(transfer.launch_url);
        window.location.href = transfer.launch_url;
        return;
      }
      const created = await api.downloads.create(sources, format, resolution, source === 'channel' ? channelId : undefined);
      const reused = created.filter(item => jobs.some(previous => previous.id === item.id)).length;
      setNotice(reused ? `${reused} arquivo(s) ou trabalho(s) existentes reaproveitados.` : 'Os novos arquivos foram adicionados à fila.');
      setJobs(prev => [...created, ...prev.filter(item => !created.some(next => next.id === item.id))]);
      setSelected([]); setLinks(''); setRefresh(n => n + 1);
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };
  const save = async (job: DownloadJob) => {
    setError('');
    try {
      // Refresh signed links immediately before delivery, even if this tab stayed open overnight.
      const fresh = await api.downloads.jobs();
      setJobs(fresh);
      const link = fresh.find(item => item.id === job.id)?.file_url;
      if (!link) throw new Error('O arquivo expirou. Solicite novamente.');
      await savePreparedFile(fresh.find(item => item.id === job.id)!);
    } catch (e) { setError(errorMessage(e)); }
  };

  return <div>
    <div className="page-heading"><div><h1>Seu acervo, para levar.</h1><p>Baixe áudio em MP3 ou vídeo em MP4 a partir de links, do seu canal ou de playlists.</p></div><span className="heading-mark"><Download size={27}/></span></div>
    {status?.mode === 'companion' && <div className="notice">Selecione os vídeos e clique em Preparar. O aplicativo abre e inicia a conversão automaticamente. Na primeira utilização neste computador, abra <strong>Iniciar Downloads.cmd</strong> uma vez para habilitar a integração.</div>}
    {transferReceived && <div className="notice">Seleção recebida do site. A preparação começa automaticamente quando o serviço estiver pronto.</div>}
    <section className="workspace-panel download-form">
      <div className="panel-top"><div><h2>Novo download</h2><p>Selecione quantos vídeos quiser. Os arquivos prontos ficam disponíveis por {status?.retention_hours || 24} horas.</p></div></div>
      <div className="download-controls">
        <div className="download-toggle" role="group" aria-label="Origem dos vídeos">
          <button aria-pressed={source === 'links'} disabled={busy} onClick={() => setSource('links')}>Por link</button>
          <button aria-pressed={source === 'channel'} disabled={busy} onClick={() => setSource('channel')}>Meu canal</button>
          <button aria-pressed={source === 'playlist'} disabled={busy} onClick={() => setSource('playlist')}>Por playlist</button>
        </div>
        {source === 'links' ? <label className="download-label">Links do YouTube<textarea aria-label="Links do YouTube" placeholder={'https://www.youtube.com/watch?v=...\nCole um link por linha'} value={links} disabled={busy} onChange={e => setLinks(e.target.value)}/><small>Vídeos, Shorts e links youtu.be. Um vídeo por linha.</small></label> : <>
          {accounts.length ? <label className="download-label">Canal conectado<select value={channelId} disabled={busy || loading} onChange={e => setChannelId(e.target.value)}>{accounts.map(account => <option key={account.id} value={account.channel_id}>{account.channel_title}</option>)}</select></label> : <div className="notice">Conecte o seu canal em Configurações para consultar seus vídeos.</div>}
          {source === 'playlist' && !!accounts.length && <>
            <label className="download-label">Playlists do canal<select value={playlists.some(playlist => playlist.id === playlistInput) ? playlistInput : ''} disabled={busy || loading || playlistOptionsLoading} onChange={e => changePlaylist(e.target.value)}><option value="">{playlistOptionsLoading ? 'Consultando playlists...' : 'Escolha uma playlist'}</option>{playlists.map(playlist => <option key={playlist.id} value={playlist.id}>{playlist.title}</option>)}</select></label>
            <label className="download-label">Ou cole o link de uma playlist<input value={playlistInput} disabled={busy || loading} placeholder="https://www.youtube.com/playlist?list=..." onChange={e => changePlaylist(e.target.value)}/></label>
            <button className="secondary-action" disabled={busy || loading || !playlistInput.trim()} onClick={loadPlaylist}>{loading ? 'Consultando...' : 'Carregar vídeos da playlist'}</button>
            <small>Também aceita playlists públicas de outros canais. Os vídeos são apresentados na ordem da playlist; você pode desmarcar os que não quiser baixar.</small>
            {playlistInfo && <div className="playlist-download-summary" role="status"><strong>{playlistInfo.title}</strong><span>{videos.length} vídeo(s) disponíveis para consulta. {playlistInfo.unavailable_count > 0 && `${playlistInfo.unavailable_count} vídeo(s) indisponíveis foram omitidos. `}{playlistInfo.duplicate_count > 0 && `${playlistInfo.duplicate_count} repetição(ões) foram removidas. `}A consulta da API não garante que vídeos privados ou restritos possam ser baixados.</span></div>}
          </>}
          {channelError && <div role="alert" className="error-note">{channelError}</div>}
          {!!accounts.length && <input className="download-search" aria-label="Buscar vídeos do canal" placeholder="Buscar no acervo do canal" value={query} onChange={e => setQuery(e.target.value)}/>}
          {!!visible.length && <div className="download-toggle"><button disabled={busy || loading} onClick={() => setSelected(prev => [...new Set([...prev, ...visible.map(video => video.id)])])}>{query ? 'Selecionar todos os resultados' : 'Selecionar todos os vídeos'}</button><button disabled={busy || !selected.length} onClick={() => setSelected([])}>Limpar seleção</button></div>}
          {loading ? <div className="notice"><Loader2 className="spin" size={18}/> Consultando vídeos...</div> : <div className="download-video-list">{visible.map(video => <label key={video.id} className="download-video"><input type="checkbox" checked={selected.includes(video.id)} disabled={busy} onChange={() => setSelected(prev => prev.includes(video.id) ? prev.filter(id => id !== video.id) : [...prev, video.id])}/>{video.thumbnail_url && <img src={video.thumbnail_url} alt=""/>}<span>{video.title}<small>{video.published_at.slice(0, 10)}</small></span></label>)}{!!accounts.length && !visible.length && !channelError && (source !== 'playlist' || playlistInfo) && <p>Nenhum vídeo encontrado.</p>}</div>}
          <small>A lista vem da API oficial. Vídeos privados ou restritos podem exigir uma sessão autorizada no servidor de downloads.</small>
        </>}
        <div className="download-format"><div className="download-toggle" role="group" aria-label="Formato do arquivo"><button aria-pressed={format === 'mp3'} disabled={busy} onClick={() => setFormat('mp3')}><Music size={17}/> MP3 · áudio</button><button aria-pressed={format === 'mp4'} disabled={busy} onClick={() => setFormat('mp4')}><Video size={17}/> MP4 · vídeo</button></div>{format === 'mp4' && <label>Qualidade máxima <select value={resolution} disabled={busy} onChange={e => setResolution(Number(e.target.value))}><option value={360}>360p</option><option value={720}>720p</option><option value={1080}>1080p</option></select></label>}</div>
        <small>{format === 'mp3' ? 'MP3 a 192 kbps. A qualidade final depende do áudio original.' : 'Vídeo com áudio. A resolução depende dos formatos disponíveis no YouTube.'}</small>
      </div>
      <div className="panel-footer"><span>{sources.length} vídeo(s) · preparação em fila</span><button className="primary-action" disabled={busy || !sources.length || loading && source !== 'links' || !status?.available || (status.mode !== 'companion' && !status.engine?.ffmpeg) || !!connectionError} onClick={submit}>{busy ? <Loader2 className="spin" size={17}/> : <Download size={17}/>} {`Preparar ${format.toUpperCase()}`}</button></div>
    </section>
    {localLink && <section className="workspace-panel download-controls"><strong>O aplicativo vai abrir e preparar sua seleção.</strong><a className="primary-action" href={launchLink}>Abrir aplicativo e iniciar</a><a className="primary-action" href={localLink} target="_blank" rel="noreferrer">Abrir seleção no aplicativo local <ExternalLink size={16}/></a><small>Autorize a abertura do aplicativo quando o navegador solicitar. Se ele ainda não estiver registrado, abra Iniciar Downloads.cmd uma vez e use Abrir aplicativo e iniciar. Se o serviço já estiver aberto, o link acima também começa automaticamente.</small></section>}
    {notice && <div className="notice" role="status">{notice}</div>}
    {(error || connectionError) && <div role="alert" className="error-note">{error || connectionError}<button className="text-action" onClick={() => { setError(''); setRefresh(n => n + 1); }}><RefreshCw size={15}/> Tentar novamente</button></div>}
    {status?.engine && <p className="download-engine-note">{status.engine.ffmpeg ? 'Conversão disponível.' : 'FFmpeg e FFprobe precisam ser instalados no servidor.'} {status.engine.auto_update ? `Motor atualizado automaticamente a cada ${status.engine.update_hours}h.` : 'Atualização automática desativada.'} {status.engine.updating && 'Verificando atualização...'} {status.engine.update_error} {!status.engine.javascript && 'Instale Node.js ou Deno no servidor para ampliar a compatibilidade com o YouTube.'}</p>}
    <details className="download-option-details"><summary>Destino e nomes dos arquivos</summary><DownloadSaveOptions/></details>
    <DownloadRetry jobs={jobs} mode={status?.mode || ''} onChanged={() => setRefresh(n => n + 1)} />
    <DownloadQueueControls jobs={jobs} mode={status?.mode || ''} onChanged={() => setRefresh(n => n + 1)} />
    <Mp3Tags jobs={jobs} mode={status?.mode || ''} onChanged={() => setRefresh(n => n + 1)}/>
    <DownloadPackages jobs={jobs} mode={status?.mode || ''} />
    {status?.mode !== 'companion' && <section className="workspace-panel download-history"><div className="panel-top"><div><h2>Seus downloads</h2><p>A preparação continua enquanto você usa as outras ferramentas.</p></div><button className="text-action" onClick={() => setRefresh(n => n + 1)}><RefreshCw size={16}/> Atualizar</button></div>
      {!jobs.length ? <div className="notice">Os arquivos preparados aparecerão aqui.</div> : jobs.map(job => <div className="download-job" key={job.id}><div className="download-job-icon">{job.format === 'mp3' ? <Music size={22}/> : <Video size={22}/>}</div><div className="download-job-info"><strong>{job.title}</strong><small>{job.format.toUpperCase()} · {statuses[job.status]} {job.file_size > 0 && `· ${(job.file_size / 1024 / 1024).toFixed(1)} MB`}</small><p>{job.message}</p>{job.status === 'running' && <progress aria-label={`Progresso de ${job.title}`} max={100} value={job.progress}/>}<a href={`https://www.youtube.com/watch?v=${job.video_id}`} target="_blank" rel="noreferrer">Ver vídeo <ExternalLink size={12}/></a></div>{job.file_url && <button className="primary-action" onClick={() => save(job)}><Download size={16}/> Salvar {job.format.toUpperCase()}</button>}{job.status === 'queued' || job.status === 'running' ? <Loader2 className="spin" size={20}/> : null}</div>)}
    </section>}
  </div>;
}
