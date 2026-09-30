import { FormEvent, useEffect, useState } from 'react';
import { api } from '../services/api';
import './AcervoForms.css';

type Result = { id: string; title: string; description: string; work: string; composer: string; arranger: string; ensemble: string; genre: string; published_at: string; identity_source: string; catalog_ambiguous: boolean; events: { name: string; project: string; performed_at: string; ensemble: string; venue: string }[] };
const blank = { q: '', work: '', composer: '', arranger: '', ensemble: '', genre: '', project: '', date_from: '', date_to: '', date_basis: 'published' };
export function AcervoSearch({ channelId }: {channelId?:string}) {
  const [accounts, setAccounts] = useState<{ channel_id: string; channel_title: string }[]>([]);
  const [channel, setChannel] = useState('');
  useEffect(() => {if(channelId) {setChannel(channelId);setItems([]);setTotal(undefined);}}, [channelId]);
  const [filters, setFilters] = useState(blank);
  const [items, setItems] = useState<Result[]>([]);
  const [total, setTotal] = useState<number>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { let current = true; api.auth.getAccounts().then(data => { if (current) { setAccounts(data); setChannel(channelId || data[0]?.channel_id || ''); } }).catch(e => { if (current) setError(String(e)); }); return () => { current = false; }; }, []);
  const change = (key: keyof typeof blank, value: string) => setFilters(old => ({ ...old, [key]: value }));
  const search = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setItems([]); setTotal(undefined);
    try {
      const query = new URLSearchParams(filters);
      const response = await fetch(`/api/acervo-search/${encodeURIComponent(channel)}?${query}`);
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Não foi possível pesquisar o canal.');
      setItems(result.items); setTotal(result.total);
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  };
  const dateLabel = (value: string) => value ? value.slice(0, 10).split('-').reverse().join('/') : 'Não cadastrada';
  return <section className="workspace-panel">
    <h2>Busca combinada</h2><p>Combine obra, créditos, filarmônica, gênero, apresentação e período. Os campos são cumulativos; a data da apresentação vem do catálogo, sem usar a publicação como substituta.</p>
    {error && <p role="alert" className="error-note">{error}</p>}
    <form onSubmit={search}><div className="acervo-form">
      {!channelId && <label>Canal<select disabled={busy} value={channel} onChange={e => { setChannel(e.target.value); setItems([]); setTotal(undefined); }}>{accounts.map(a => <option key={a.channel_id} value={a.channel_id}>{a.channel_title}</option>)}</select></label>}
      <label>Buscar em título e descrição<input disabled={busy} value={filters.q} onChange={e => change('q', e.target.value)} placeholder="Palavras ou trecho"/></label>
      {([['work', 'Obra'], ['composer', 'Compositor'], ['arranger', 'Arranjador'], ['ensemble', 'Filarmônica'], ['genre', 'Gênero'], ['project', 'Projeto ou apresentação']] as const).map(([key, label]) => <label key={key}>{label}<input disabled={busy} value={filters[key]} onChange={e => change(key, e.target.value)}/></label>)}
      <label>Tipo de data<select disabled={busy} value={filters.date_basis} onChange={e => change('date_basis', e.target.value)}><option value="published">Publicação no YouTube</option><option value="performed">Data da apresentação</option></select></label>
      <label>De<input disabled={busy} type="date" value={filters.date_from} onChange={e => change('date_from', e.target.value)}/></label>
      <label>Até<input disabled={busy} type="date" value={filters.date_to} onChange={e => change('date_to', e.target.value)}/></label>
    </div><div className="acervo-actions"><button disabled={busy || !channel} type="submit">{busy ? 'Pesquisando…' : 'Pesquisar acervo'}</button><button disabled={busy} type="button" onClick={() => { setFilters(blank); setItems([]); setTotal(undefined); }}>Limpar filtros</button></div></form>
    {total !== undefined && <p role="status">{items.length} resultado(s) em {total} vídeos. Mais recentes primeiro.</p>}
    <div className="acervo-record-list">{items.map(item => <article className="acervo-record" key={item.id}>
      <a href={`https://www.youtube.com/watch?v=${encodeURIComponent(item.id)}`} target="_blank" rel="noreferrer"><strong>{item.title}</strong></a>
      <p>{[item.genre, item.work, item.composer, item.arranger && `Arr. ${item.arranger}`, item.ensemble].filter(Boolean).join(' · ')}</p>
      <small>Identificação: {item.identity_source === 'catalog' ? 'obra revisada no catálogo' : 'extraída do título e descrição; confira os créditos'}{item.catalog_ambiguous ? ' (mais de um registro no catálogo)' : ''}</small>
      <p>Publicado em {dateLabel(item.published_at)}</p>
      {item.events.map((event, index) => <p key={index}>{event.name} · {event.ensemble} · Apresentação: {dateLabel(event.performed_at)}{event.venue ? ` · ${event.venue}` : ''}</p>)}
      <details><summary>Ver descrição atual</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', fontFamily: 'inherit' }}>{item.description || '(Sem descrição)'}</pre></details>
    </article>)}</div>
    {total !== undefined && !items.length && <p>Nenhum vídeo corresponde à combinação. Reduza os filtros para ampliar a busca.</p>}
  </section>;
}
