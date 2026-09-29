import { useEffect, useMemo, useState } from 'react';
import { ArrowRight, Check, ChevronDown, ExternalLink, Loader2, RefreshCw, Search, Sparkles } from 'lucide-react';
import { api } from '../services/api';
import { Account, ApplyResult, DescriptionProposal, EmptyVideo } from '../types';

type Identity = { work: string; composer: string; arranger: string };
const labels = { same_work: 'Mesma obra', composer: 'Mesmo compositor', arranger: 'Mesmo arranjador', none: 'Sem referência segura' };

export function DescriptionsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [channelId, setChannelId] = useState('');
  const [videos, setVideos] = useState<EmptyVideo[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [overrides, setOverrides] = useState<Record<string, Identity>>({});
  const [proposals, setProposals] = useState<DescriptionProposal[]>([]);
  const [activeId, setActiveId] = useState('');
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState<'load' | 'preview' | 'apply' | ''>('');
  const [error, setError] = useState('');
  const [results, setResults] = useState<ApplyResult[]>([]);

  useEffect(() => {
    api.auth.getAccounts().then(data => { setAccounts(data); setChannelId(data[0]?.channel_id || ''); }).catch(e => setError(String(e)));
  }, []);
  useEffect(() => {
    if (!channelId) return;
    setVideos([]); setSelected([]); setProposals([]); setResults([]);
    setBusy('load'); setError('');
    api.descriptions.empty(channelId).then(setVideos).catch(e => setError(String(e))).finally(() => setBusy(''));
  }, [channelId]);

  const visible = useMemo(() => videos.filter(v => v.title.toLocaleLowerCase().includes(query.toLocaleLowerCase())), [videos, query]);
  const active = proposals.find(p => p.video_id === activeId) || proposals[0];
  const chosen = proposals.filter(p => p.description.trim());
  const toggle = (id: string) => { setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]); setProposals([]); };
  const setIdentity = (id: string, key: keyof Identity, value: string) => {
    setOverrides(prev => ({ ...prev, [id]: { work: prev[id]?.work || '', composer: prev[id]?.composer || '', arranger: prev[id]?.arranger || '', [key]: value } }));
    setProposals([]);
  };
  const preview = async () => {
    setBusy('preview'); setError(''); setResults([]);
    try { const data = await api.descriptions.preview(channelId, selected, overrides); setProposals(data); setActiveId(data[0]?.video_id || ''); }
    catch (e) { setError(String(e)); }
    finally { setBusy(''); }
  };
  const apply = async () => {
    if (!chosen.length || !window.confirm(`Publicar ${chosen.length} descrição(ões) no canal?`)) return;
    setBusy('apply'); setError('');
    try {
      const data = await api.descriptions.apply(channelId, chosen.map(p => ({ video_id: p.video_id, description: p.description })));
      setResults(data);
      const updated = new Set(data.filter(r => r.status === 'updated').map(r => r.video_id));
      setVideos(prev => prev.filter(v => !updated.has(v.id)));
      setSelected(prev => prev.filter(id => !updated.has(id)));
      setProposals(prev => prev.filter(p => !updated.has(p.video_id)));
    } catch (e) { setError(String(e)); }
    finally { setBusy(''); }
  };

  return <div className="descriptions-page">
    <div className="page-heading"><div><h1>Descrições em dia.</h1><p>Encontre referências no seu acervo, atualize os links e publique em lote.</p></div><span className="heading-mark"><Sparkles size={27}/></span></div>
    <div className="workflow"><span className="current">Selecionar vídeos</span><ArrowRight size={16}/><span className={proposals.length ? 'current' : ''}>Conferir sugestões</span><ArrowRight size={16}/><span>Publicar no canal</span></div>
    <section className="workspace-panel">
      <div className="panel-top"><div><h2>Vídeos sem descrição</h2><p>O acervo do canal é consultado diretamente pela API do YouTube.</p></div>{accounts.length > 0 && <div className="channel-picker"><label htmlFor="channel">Canal conectado</label><div><select id="channel" value={channelId} onChange={e => setChannelId(e.target.value)}>{accounts.map(a => <option key={a.channel_id} value={a.channel_id}>{a.channel_title}</option>)}</select><ChevronDown size={15}/></div></div>}</div>
      {!accounts.length && !busy && <div className="notice">Nenhum canal conectado. Abra Configurações para conectar sua conta do YouTube.</div>}
      {accounts.length > 0 && <><div className="list-toolbar"><div className="search-box"><Search size={18}/><input aria-label="Buscar vídeos" placeholder="Buscar entre os vídeos sem descrição" value={query} onChange={e => setQuery(e.target.value)}/></div><button className="text-action" onClick={() => { setBusy('load'); api.descriptions.empty(channelId).then(setVideos).catch(e => setError(String(e))).finally(() => setBusy('')); }}><RefreshCw size={16}/> Atualizar</button></div>
      {busy === 'load' ? <div className="notice"><Loader2 className="spin" size={19}/> Lendo o acervo completo...</div> : visible.length ? <div className="video-list">{visible.map(v => <div className={`video-row ${selected.includes(v.id) ? 'selected' : ''}`} key={v.id}><label className="video-main"><input type="checkbox" checked={selected.includes(v.id)} onChange={() => toggle(v.id)}/><img src={v.thumbnail_url || `https://img.youtube.com/vi/${v.id}/mqdefault.jpg`} alt=""/><span><strong>{v.title}</strong><small>{v.published_at.slice(0, 10)} · <a href={`https://www.youtube.com/watch?v=${v.id}`} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}>Ver no YouTube <ExternalLink size={12}/></a></small></span></label>{selected.includes(v.id) && <div className="identity-fields"><input aria-label={`Obra de ${v.title}`} placeholder="Obra (se o título não bastar)" value={overrides[v.id]?.work || ''} onChange={e => setIdentity(v.id, 'work', e.target.value)}/><input aria-label={`Compositor de ${v.title}`} placeholder="Compositor" value={overrides[v.id]?.composer || ''} onChange={e => setIdentity(v.id, 'composer', e.target.value)}/><input aria-label={`Arranjador de ${v.title}`} placeholder="Arranjador" value={overrides[v.id]?.arranger || ''} onChange={e => setIdentity(v.id, 'arranger', e.target.value)}/></div>}</div>)}</div> : <div className="notice">{videos.length ? 'Nenhum vídeo corresponde à busca.' : 'Nenhum vídeo sem descrição neste canal.'}</div>}
      <div className="panel-footer"><span>{selected.length} selecionado{selected.length === 1 ? '' : 's'} · até 50 por lote</span><button className="primary-action" disabled={!selected.length || selected.length > 50 || !!busy} onClick={preview}>{busy === 'preview' ? <Loader2 className="spin" size={17}/> : <Sparkles size={17}/>} Buscar descrições <ArrowRight size={17}/></button></div></>}
    </section>
    {error && <div role="alert" className="error-note">{error}</div>}
    {proposals.length > 0 && <section className="review-section"><div className="review-heading"><div><h2>Conferir sugestões</h2><p>Edite o texto quando precisar. Apenas sugestões com texto serão publicadas.</p></div><span>{chosen.length} prontas de {proposals.length}</span></div><div className="review-layout"><div className="review-list">{proposals.map(p => <button key={p.video_id} className={active?.video_id === p.video_id ? 'active' : ''} onClick={() => setActiveId(p.video_id)}><span className={`match-dot ${p.match_type}`}/><span><strong>{p.title}</strong><small>{labels[p.match_type]}</small></span>{p.description && <Check size={17}/>}</button>)}</div>{active && <div className="review-editor"><div className="review-meta"><span className={`match-label ${active.match_type}`}>{labels[active.match_type]}</span><strong>{active.title}</strong><p>{active.reason}</p>{active.source && <a href={`https://www.youtube.com/watch?v=${active.source.id}`} target="_blank" rel="noreferrer">Texto da obra / pessoa: {active.source.title} <ExternalLink size={13}/></a>}{active.links_source && <a href={`https://www.youtube.com/watch?v=${active.links_source.id}`} target="_blank" rel="noreferrer">Links recentes: {active.links_source.title} <ExternalLink size={13}/></a>}</div><label htmlFor="description-editor">Descrição proposta</label><textarea id="description-editor" value={active.description} maxLength={5000} placeholder="Nenhuma sugestão segura. Você pode escrever a descrição aqui." onChange={e => setProposals(prev => prev.map(p => p.video_id === active.video_id ? { ...p, description: e.target.value } : p))}/><small>{active.description.length} / 5000 caracteres</small></div>}</div><div className="publish-row"><span>Vídeos que ganharam descrição depois da prévia serão ignorados.</span><button className="primary-action" disabled={!chosen.length || !!busy} onClick={apply}>{busy === 'apply' ? <Loader2 className="spin" size={17}/> : <Check size={17}/>} Publicar {chosen.length} descrição(ões)</button></div></section>}
    {results.length > 0 && <div className="result-panel" role="status"><h2>Resultado da publicação</h2>{results.map(r => <p key={r.video_id}><strong>{r.status === 'updated' ? 'Publicado' : r.status === 'skipped' ? 'Ignorado' : 'Erro'}</strong> · {r.video_id}: {r.message}</p>)}</div>}
  </div>;
}
