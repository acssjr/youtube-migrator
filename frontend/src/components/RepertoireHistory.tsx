import { useEffect, useMemo, useState } from 'react';
import { groupRepertoire, type CatalogItem } from '../services/repertoireHistory';
const normalized = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').replace(/\s+/g, ' ').trim();
const displayDate = (value?: string) => value ? value.slice(0, 10).split('-').reverse().join('/') : 'Sem data cadastrada';

export default function RepertoireHistory({ channelId }: { channelId: string }) {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [ensemble, setEnsemble] = useState('');
  const [composer, setComposer] = useState('');
  const [genre, setGenre] = useState('');
  const [query, setQuery] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [basis, setBasis] = useState<'performed' | 'published'>('performed');
  const [count, setCount] = useState('all');
  useEffect(() => {
    setItems([]); setError('');
    if (!channelId) { setLoading(false); return; }
    const controller = new AbortController();
    setLoading(true);
    fetch(`/api/acervo-search/${encodeURIComponent(channelId)}`, { signal: controller.signal }).then(async response => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Não foi possível carregar o repertório.');
      setItems(data.items || []);
    }).catch(reason => { if (reason.name !== 'AbortError') setError(reason.message); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [channelId, refresh]);
  const groups = useMemo(() => groupRepertoire(items), [items]);
  const options = (field: 'ensemble' | 'composer' | 'genre') => [...new Set(groups.map(group => group[field]).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'pt-BR'));
  const invalidRange = Boolean(dateFrom && dateTo && dateFrom > dateTo);
  const filtered = groups.filter(group => {
    const dates = basis === 'performed' ? group.performedDates : group.publishedDates;
    return (!ensemble || normalized(group.ensemble) === normalized(ensemble)) && (!composer || normalized(group.composer) === normalized(composer)) && (!genre || normalized(group.genre) === normalized(genre)) && (!query || normalized([group.work, group.composer, group.arranger].join(' ')).includes(normalized(query))) && (count === 'all' || (count === 'single' ? group.recordings.length === 1 : group.recordings.length > 1)) && !invalidRange && (!(dateFrom || dateTo) || dates.some(date => (!dateFrom || date >= dateFrom) && (!dateTo || date <= dateTo)));
  }).sort((a, b) => {
    const aDates = basis === 'performed' ? a.performedDates : a.publishedDates;
    const bDates = basis === 'performed' ? b.performedDates : b.publishedDates;
    return (bDates[bDates.length - 1] || '').localeCompare(aDates[aDates.length - 1] || '') || a.work.localeCompare(b.work, 'pt-BR');
  });
  return <section className="workspace-panel">
    <h2>Histórico do repertório</h2>
    <p>Veja as obras documentadas por filarmônica e arranjo. Uma única gravação indica uma primeira referência no canal; não comprova que a obra nunca foi tocada antes.</p>
    {!channelId && <p>Selecione um canal para consultar o repertório.</p>}
    <div className="acervo-form">
      <label>Filarmônica<select value={ensemble} onChange={event => setEnsemble(event.target.value)}><option value="">Todas</option>{options('ensemble').map(value => <option key={value}>{value}</option>)}</select></label>
      <label>Compositor<select value={composer} onChange={event => setComposer(event.target.value)}><option value="">Todos</option>{options('composer').map(value => <option key={value}>{value}</option>)}</select></label>
      <label>Gênero<select value={genre} onChange={event => setGenre(event.target.value)}><option value="">Todos</option>{options('genre').map(value => <option key={value}>{value}</option>)}</select></label>
      <label>Obra ou arranjador<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Pesquisar repertório" /></label>
      <label>Referência de data<select value={basis} onChange={event => setBasis(event.target.value as typeof basis)}><option value="performed">Apresentação cadastrada</option><option value="published">Publicação no YouTube</option></select></label>
      <label>Desde<input type="date" value={dateFrom} onChange={event => setDateFrom(event.target.value)} /></label>
      <label>Até<input type="date" value={dateTo} onChange={event => setDateTo(event.target.value)} /></label>
      <label>Quantidade de registros<select value={count} onChange={event => setCount(event.target.value)}><option value="all">Todas as obras</option><option value="single">Uma gravação no canal</option><option value="repeated">Mais de uma gravação</option></select></label>
    </div>
    <div className="acervo-actions"><button disabled={loading || !channelId} onClick={() => setRefresh(value => value + 1)}>Atualizar repertório</button><span>{filtered.length} obras / arranjos</span></div>
    {loading && <p role="status">Consultando o acervo do canal…</p>}{error && <p role="alert">{error}</p>}{invalidRange && <p role="alert">A data inicial precisa ser anterior à final.</p>}
    {!loading && !error && channelId && filtered.length === 0 && <p>Nenhum registro encontrado para estes filtros.</p>}
    <div className="acervo-record-list">{filtered.map(group => <article className="acervo-record" key={group.key}>
      <h3>{group.work || 'Obra não identificada'}</h3><p>{group.ensemble} · {group.composer || 'Compositor não identificado'}{group.arranger && ` · Arr. ${group.arranger}`}</p>
      <p>{group.recordings.length} {group.recordings.length === 1 ? 'gravação documentada' : 'gravações documentadas'}{group.genre && ` · ${group.genre}`}</p>
      <p>Primeira apresentação com data: {displayDate(group.performedDates[0])}<br />Última apresentação com data: {displayDate(group.performedDates[group.performedDates.length - 1])}</p>
      <small>Primeira publicação: {displayDate(group.publishedDates[0])} · Última publicação: {displayDate(group.publishedDates[group.publishedDates.length - 1])}</small>
      <details><summary>Ver gravações e apresentações</summary>{group.recordings.map(record => <div key={record.id} style={{ margin: '14px 0' }}><a href={`https://www.youtube.com/watch?v=${encodeURIComponent(record.id)}`} target="_blank" rel="noreferrer">{record.title}</a><p>Publicado em {displayDate(record.published_at)}</p>{record.events.filter(event => !event.ensemble || normalized(event.ensemble) === normalized(group.ensemble)).map((event, index) => <p key={index}>{event.name}{event.project && ` · ${event.project}`} · Apresentação: {displayDate(event.performed_at)}{event.venue && ` · ${event.venue}`}</p>)}{record.events.length === 0 && <small>Apresentação ainda não cadastrada.</small>}</div>)}</details>
    </article>)}</div>
  </section>;
}
