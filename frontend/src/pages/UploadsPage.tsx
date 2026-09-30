import { EnsemblePresets } from '../components/EnsemblePresets';
import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { ExternalLink, Pause, Play, Plus, Sparkles, Trash2, Upload, Loader2 } from 'lucide-react';
import { api } from '../services/api';
import { Account } from '../types';
import { NamePicker } from '../components/NamePicker';
import { BatchPlaylist } from '../components/BatchPlaylist';
import { composeUploadTitle, Privacy, UploadItem, uploadQueue } from '../services/uploadQueue';

const privacyLabels = { private: 'Privado', unlisted: 'Não listado', public: 'Público' };
const statusLabels = { draft: 'Aguardando', uploading: 'Enviando', paused: 'Pausado', error: 'Falha no envio', completed: 'Enviado ao YouTube' };
const matchLabels = { same_work: 'Mesma obra', composer: 'Mesmo compositor', arranger: 'Mesmo arranjador', none: 'Sem referência segura' };
const genres = ['Dobrado', 'Marcha', 'Maxixe', 'Valsa', 'Bolero', 'Fantasia', 'Suíte', 'Hino', 'Polca', 'Samba', 'Choro', 'Frevo', 'Seleção', 'Pot-pourri'];
const sizeLabel = (bytes: number) => bytes >= 1024 ** 3 ? `${(bytes / 1024 ** 3).toFixed(2)} GB` : `${(bytes / 1024 ** 2).toFixed(1)} MB`;

export function UploadsPage() {
  const queue = useSyncExternalStore(uploadQueue.subscribe, uploadQueue.snapshot);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [catalog, setCatalog] = useState({ composers: [] as string[], arrangers: [] as string[], ensembles: [] as string[] });
  const [catalogBusy, setCatalogBusy] = useState(false);
  const [privacy, setPrivacy] = useState<Privacy>('private');
  const [ensemble, setEnsemble] = useState('');
  const [titlePreferences, setTitlePreferences] = useState<UploadItem['titlePreferences']>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [customGenres, setCustomGenres] = useState<Record<string, boolean>>({});
  const fileInput = useRef<HTMLInputElement>(null);
  const channelId = queue.channelId || accounts[0]?.channel_id || '';
  const pending = queue.items.filter(item => item.included && item.status !== 'completed');
  const selectedSize = pending.reduce((sum, item) => sum + item.size, 0);

  useEffect(() => { api.auth.getAccounts().then(setAccounts).catch(e => setError(String(e))); }, []);
  useEffect(() => {
    if (!channelId) return;
    let current = true;
    setCatalogBusy(true); setCatalog({ composers: [], arrangers: [], ensembles: [] });
    api.uploads.catalog(channelId).then(data => { if (current) setCatalog(data); })
      .catch(e => { if (current) setError(String(e)); }).finally(() => { if (current) setCatalogBusy(false); });
    return () => { current = false; };
  }, [channelId]);

  const change = (item: UploadItem, patch: Partial<UploadItem>) => {
    const next = { ...item, ...patch };
    const fromReference = !!item.proposal && item.description === item.proposal.description;
    uploadQueue.patch(item.id, { ...patch, title: composeUploadTitle(next), proposal: undefined, ...(fromReference ? { description: '' } : {}) });
  };
  const preview = async () => {
    if (pending.some(item => !item.identity.work.trim() || !item.title.trim() || item.title.length > 100)) { setError('Preencha o nome das obras e confira os títulos antes de buscar descrições.'); return; }
    const drafts = pending.filter(item => !item.sessionUrl);
    if (!drafts.length) return;
    if (drafts.some(item => item.description.trim()) && !window.confirm('Substituir as descrições desses arquivos pelas novas sugestões?')) return;
    setBusy(true); setError('');
    try {
      const proposals = await api.uploads.preview(channelId, drafts.map(item => ({ id: item.id, title: item.title, identity: { ...item.identity, work: [item.genre, item.identity.work].filter(Boolean).join(' ') } })));
      proposals.forEach(proposal => uploadQueue.patch(proposal.video_id, { proposal, description: proposal.description }));
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  };
  const start = async () => { setError(''); try { await uploadQueue.start(); } catch (e) { setError(String(e)); } };
  const names = (kind: 'composers' | 'arrangers' | 'ensembles') => [...new Set([...catalog[kind], ...queue.items.map(item => kind === 'ensembles' ? item.ensemble : kind === 'composers' ? item.identity.composer : item.identity.arranger)])].filter(Boolean).sort((a, b) => a.localeCompare(b, 'pt-BR'));

  return <div className="uploads-page">
    <div className="page-heading"><div><h1>Seu próximo lote.</h1><p>Prepare os títulos, confira as descrições e envie os vídeos em fila.</p></div><span className="heading-mark"><Upload size={27}/></span></div>
    <div className="workflow"><span className="current">Escolher arquivos</span><span>→</span><span>Preparar informações</span><span>→</span><span>Enviar ao YouTube</span></div>
    <section className="workspace-panel">
      <div className="panel-top"><div><h2>Upload em lote</h2><p>Os arquivos vão do seu navegador diretamente ao YouTube.</p></div><div className="channel-picker"><label htmlFor="upload-channel">Canal de destino</label><select id="upload-channel" value={channelId} disabled={queue.running || queue.items.length > 0 || busy} onChange={e => uploadQueue.setChannel(e.target.value)}>{accounts.map(account => <option key={account.channel_id} value={account.channel_id}>{account.channel_title}</option>)}</select></div></div>
      {!accounts.length ? <div className="notice">Conecte o canal em Configurações para preparar seu lote.</div> : <>
        <div className="upload-defaults">
          <label>Visibilidade para novos arquivos<select value={privacy} disabled={queue.running || busy} onChange={e => setPrivacy(e.target.value as Privacy)}>{Object.entries(privacyLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
          <label>Filarmônica do lote<NamePicker label="Filarmônica do lote" options={names('ensembles')} value={ensemble} disabled={queue.running || busy} onChange={setEnsemble}/></label>
          <button className="text-action" disabled={queue.running || busy || !queue.items.length} onClick={() => queue.items.filter(item => !item.sessionUrl && item.status !== 'completed').forEach(item => change(item, { ensemble, privacy }))}>Aplicar ao lote</button>
        </div>
        <div className="upload-select"><button className="primary-action" disabled={queue.running || busy} onClick={() => fileInput.current?.click()}><Plus size={17}/> {queue.items.some(item => !uploadQueue.hasFile(item.id) && item.status !== 'completed') ? 'Selecionar / reconectar arquivos' : 'Selecionar vídeos'}</button><span>Até 50 arquivos · {catalogBusy ? 'Lendo nomes do acervo…' : `${catalog.composers.length} compositores no acervo`}</span><input ref={fileInput} type="file" multiple accept="video/*,.mkv,.mts,.m2ts,.m4v" hidden onChange={event => { uploadQueue.add(Array.from(event.target.files || []), privacy, channelId, ensemble, titlePreferences); event.target.value = ''; }}/></div>
      </>}
    </section>
    <details className="workspace-panel"><summary>Cadastros e preferências das filarmônicas</summary><EnsemblePresets onApply={payload => {
      if (queue.running || busy) {setError('Pause o lote antes de aplicar preferências.');return;}
      setEnsemble(payload.name); setPrivacy(payload.privacy); setTitlePreferences(payload.titlePreferences);
      queue.items.filter(item => !item.sessionUrl && item.status !== 'completed').forEach(item => change(item, {ensemble:payload.name,privacy:payload.privacy,titlePreferences:payload.titlePreferences}));
    }}/></details>
    {(error || queue.storageError) && <div role="alert" className="error-note">{error || queue.storageError}</div>}
    {queue.items.length > 0 && <>
      <div className="upload-batch-actions"><span>{pending.length} na fila · {sizeLabel(selectedSize)}</span><button className="text-action" disabled={queue.running || busy || !pending.some(item => !item.sessionUrl)} onClick={preview}>{busy ? <Loader2 className="spin" size={17}/> : <Sparkles size={17}/>} Buscar descrições no acervo</button><button className="text-action" disabled={queue.running || busy} onClick={() => { if (window.confirm('Limpar os rascunhos e o histórico deste lote? Vídeos já enviados continuam no YouTube.')) uploadQueue.clear(); }}><Trash2 size={16}/> Limpar lote</button></div>
      {queue.items.map((item, index) => {
        const locked = queue.running || busy || !!item.sessionUrl || item.status === 'completed';
        const percent = Math.min(100, Math.round(item.bytes / item.size * 100));
        return <section className={`workspace-panel upload-card ${item.status}`} key={item.id}>
          <div className="upload-file-heading"><label><input type="checkbox" checked={item.included} disabled={queue.running || busy || item.status === 'completed'} onChange={e => uploadQueue.patch(item.id, { included: e.target.checked })}/><span className="upload-index">{String(index + 1).padStart(2, '0')}</span><span><strong>{item.name}</strong><small>{sizeLabel(item.size)} · {statusLabels[item.status]}{item.status !== 'completed' && !uploadQueue.hasFile(item.id) ? ' · Selecione novamente o arquivo original' : ''}</small></span></label><button aria-label={`Remover ${item.name}`} className="text-action" disabled={queue.running || busy} onClick={() => { if (!item.sessionUrl || window.confirm('Remover este envio interrompido da fila? Antes de enviar novamente, confira se ele já apareceu no canal.')) uploadQueue.remove(item.id); }}><Trash2 size={16}/></button></div>
          {item.status !== 'completed' && <div className="upload-fields">
            <div className="genre-picker"><span>Gênero <small>opcional</small></span><div role="group" aria-label={`Gênero de ${item.name}`}>{['', ...genres].map(genre => <button type="button" key={genre} aria-pressed={item.genre === genre} disabled={locked} onClick={() => { change(item, { genre }); setCustomGenres(prev => ({ ...prev, [item.id]: false })); }}>{genre || 'Sem gênero'}</button>)}<button type="button" aria-pressed={!!customGenres[item.id] || (!!item.genre && !genres.includes(item.genre))} disabled={locked} onClick={() => setCustomGenres(prev => ({ ...prev, [item.id]: true }))}>Outro</button></div>{(customGenres[item.id] || (!!item.genre && !genres.includes(item.genre))) && <label>Outro gênero<input value={item.genre} disabled={locked} placeholder="Digite o gênero" onChange={event => change(item, { genre: event.target.value })}/></label>}</div>
            <label className="upload-work">Nome da obra <small>obrigatório</small><input value={item.identity.work} disabled={locked} placeholder="Allah" onChange={e => change(item, { identity: { ...item.identity, work: e.target.value } })}/></label>
            <label>Compositor<NamePicker label={`Compositor de ${item.name}`} options={names('composers')} value={item.identity.composer} disabled={locked} onChange={composer => change(item, { identity: { ...item.identity, composer } })}/></label>
            <label>Filarmônica<NamePicker label={`Filarmônica de ${item.name}`} options={names('ensembles')} value={item.ensemble} disabled={locked} onChange={ensemble => change(item, { ensemble })}/></label>
            <label>Arranjador <small>opcional</small><NamePicker label={`Arranjador de ${item.name}`} options={names('arrangers')} value={item.identity.arranger} disabled={locked} onChange={arranger => change(item, { identity: { ...item.identity, arranger } })}/></label>
            <label>Visibilidade<select value={item.privacy} disabled={locked} onChange={e => uploadQueue.patch(item.id, { privacy: e.target.value as Privacy })}>{Object.entries(privacyLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
            <label>Conteúdo para crianças<select value={item.madeForKids ? 'yes' : 'no'} disabled={locked} onChange={e => uploadQueue.patch(item.id, { madeForKids: e.target.value === 'yes' })}><option value="no">Não, não é feito para crianças</option><option value="yes">Sim, é feito para crianças</option></select></label>
          </div>}
          <div className="upload-title"><span>Título no YouTube <small className={item.title.length > 100 ? 'invalid' : ''}>{item.title.length}/100</small></span><strong>{item.title || 'Preencha o nome da obra para montar o título.'}</strong>{item.status !== 'completed' && <details><summary>Ajustar o título completo</summary><input aria-label={`Título completo de ${item.name}`} value={item.title} disabled={locked} maxLength={100} onChange={e => uploadQueue.patch(item.id, { title: e.target.value, proposal: undefined, ...(item.proposal && item.description === item.proposal.description ? { description: '' } : {}) })}/><small>Alterar os campos acima volta a montar o título automaticamente.</small></details>}</div>
          {item.status !== 'completed' && <div className="upload-description"><label htmlFor={`description-${item.id}`}>Descrição <small>{item.description.length}/5000</small></label>{item.proposal && <div className="upload-reference"><span>{matchLabels[item.proposal.match_type]}</span>{item.proposal.source && <a href={`https://www.youtube.com/watch?v=${item.proposal.source.id}`} target="_blank" rel="noreferrer">{item.proposal.source.title} <ExternalLink size={12}/></a>}{item.proposal.links_source && <a href={`https://www.youtube.com/watch?v=${item.proposal.links_source.id}`} target="_blank" rel="noreferrer">Referência dos links e playlists <ExternalLink size={12}/></a>}</div>}<textarea id={`description-${item.id}`} disabled={locked} value={item.description} maxLength={5000} placeholder="Busque uma referência no acervo ou escreva a descrição. O envio também pode ser feito sem descrição." onChange={e => uploadQueue.patch(item.id, { description: e.target.value })}/></div>}
          {(item.bytes > 0 || item.status !== 'draft') && <div className="upload-progress" role="status"><progress value={item.bytes} max={item.size}/><span>{percent}% · {statusLabels[item.status]}</span>{item.error && <p className="invalid">{item.error}</p>}{item.videoId && <><a href={`https://www.youtube.com/watch?v=${item.videoId}`} target="_blank" rel="noreferrer">Ver vídeo enviado <ExternalLink size={13}/></a><p>Visibilidade confirmada: {privacyLabels[item.actualPrivacy as Privacy] || 'não informada pelo YouTube'} · o YouTube ainda pode estar processando o vídeo.</p>{item.actualPrivacy && item.actualPrivacy !== item.privacy && <p className="invalid">Você solicitou {privacyLabels[item.privacy].toLowerCase()}, mas o YouTube confirmou {privacyLabels[item.actualPrivacy as Privacy]?.toLowerCase() || item.actualPrivacy}.</p>}</>}</div>}
          {item.status === 'error' && item.sessionUrl && !queue.running && <div className="upload-description"><button className="text-action" onClick={() => {
            if (window.confirm('Confira primeiro se este vídeo já apareceu no canal. Reiniciar cria uma nova sessão e pode duplicar um vídeo que já foi concluído. Reiniciar este arquivo?')) uploadQueue.patch(item.id, { sessionUrl: undefined, status: 'draft', bytes: 0, error: '' });
          }}>Reiniciar sessão deste arquivo</button></div>}
        </section>;
      })}
      <div className="upload-start"><div><strong>Confira as informações antes de enviar.</strong><p>Mantenha esta aba aberta. A fila continua ao trocar de ferramenta neste site. Após recarregar, selecione novamente os arquivos originais para retomar.</p><small>Projetos de API sem auditoria podem ter os uploads limitados a privados pelo YouTube. <a href="https://developers.google.com/youtube/v3/docs/videos/insert" target="_blank" rel="noreferrer">Entenda a restrição</a>.</small></div>{queue.running ? <button className="primary-action" onClick={uploadQueue.pause}><Pause size={17}/> Pausar fila</button> : <button className="primary-action" disabled={busy || !pending.length || !accounts.some(account => account.channel_id === channelId)} onClick={start}><Play size={17}/> Enviar {pending.length} vídeo(s)</button>}</div>
    </>}
    {queue.items.some(item => item.status === 'completed' && item.videoId) && <BatchPlaylist channelId={channelId} ensemble={queue.items.find(item => item.ensemble)?.ensemble || ensemble} videos={queue.items.filter(item => item.status === 'completed' && item.videoId).map(item => ({ id: item.videoId!, title: item.title }))}/>}
  </div>;
}
