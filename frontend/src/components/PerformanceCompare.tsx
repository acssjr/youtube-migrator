import { useEffect, useMemo, useRef, useState } from 'react';
import { acervoApi, type AcervoRecord } from '../services/acervoApi';

interface Performance {
  id: string; title: string; description: string; work: string; composer: string; arranger: string;
  genre: string; ensemble: string; published_at: string; catalog_ambiguous?: boolean;
  events: { name: string; performed_at: string; ensemble: string; venue: string }[];
}
interface Favorite { channel_id: string; video_id: string; title: string; notes: string; favorite: boolean }
const normalized = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').replace(/[^a-z0-9]+/g, ' ').trim();
const identityKey = (item: Performance) => JSON.stringify([normalized(item.work), normalized(item.composer), normalized(item.arranger)]);
const dateLabel = (value: string) => value ? value.slice(0, 10).split('-').reverse().join('/') : 'Não cadastrada';

export default function PerformanceCompare({ channelId }: { channelId: string }) {
  const channelRef = useRef(channelId);
  channelRef.current = channelId;
  const [items, setItems] = useState<Performance[]>([]);
  const [favorites, setFavorites] = useState<AcervoRecord<Favorite>[]>([]);
  const [group, setGroup] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [opened, setOpened] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [onlyFavorites, setOnlyFavorites] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setItems([]); setFavorites([]); setGroup(''); setSelected([]); setOpened([]); setDrafts({}); setError(''); setNotice('');
    if (!channelId) return () => controller.abort();
    setLoading(true);
    Promise.all([
      fetch(`/api/acervo-search/${encodeURIComponent(channelId)}`, { signal: controller.signal }).then(async response => {
        const result = await response.json();
        if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Não foi possível carregar as execuções.');
        return result.items as Performance[];
      }),
      acervoApi.records<Favorite>('favorite'),
    ]).then(([videos, records]) => {
      if (controller.signal.aborted) return;
      setItems(videos); setFavorites(records.filter(record => record.payload.channel_id === channelId));
    }).catch(reason => { if (!controller.signal.aborted) setError(reason.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [channelId]);

  const favoriteMap = useMemo(() => new Map(favorites.slice().sort((a, b) => a.updated_at.localeCompare(b.updated_at)).map(record => [record.payload.video_id, record])), [favorites]);
  const groups = useMemo(() => {
    const result = new Map<string, Performance[]>();
    items.filter(item => item.work && item.composer && !item.catalog_ambiguous).forEach(item => {
      const key = identityKey(item); result.set(key, [...(result.get(key) || []), item]);
    });
    return [...result.entries()].filter(([, videos]) => videos.length > 1).sort((a, b) => a[1][0].work.localeCompare(b[1][0].work, 'pt-BR'));
  }, [items]);
  const candidates = (group ? items.filter(item => identityKey(item) === group && !item.catalog_ambiguous) : items)
    .filter(item => !onlyFavorites || favoriteMap.get(item.id)?.payload.favorite)
    .filter(item => !query || normalized(`${item.title} ${item.work} ${item.composer} ${item.ensemble}`).includes(normalized(query)));
  const comparison = items.filter(item => selected.includes(item.id));

  async function save(item: Performance, favorite: boolean) {
    const activeChannel = channelId;
    const record = favoriteMap.get(item.id);
    const payload: Favorite = { channel_id: activeChannel, video_id: item.id, title: item.title, notes: drafts[item.id] ?? record?.payload.notes ?? '', favorite };
    setSaving(item.id); setError(''); setNotice('');
    try {
      const updated = record ? await acervoApi.update(record.id, payload, record.updated_at) : await acervoApi.create('favorite', payload);
      if (channelRef.current !== activeChannel) return;
      setFavorites(current => [...current.filter(entry => entry.id !== updated.id), updated]);
      setNotice('Favorito e anotação salvos no acervo.');
    } catch (reason) { if (channelRef.current === activeChannel) setError(reason instanceof Error ? reason.message : 'Não foi possível salvar.'); }
    finally { setSaving(''); }
  }

  function toggleComparison(item: Performance) {
    if (selected.includes(item.id)) { setSelected(current => current.filter(id => id !== item.id)); return; }
    if (!item.work || !item.composer || item.catalog_ambiguous) { setError('Cadastre a obra e o compositor antes de comparar esta execução.'); return; }
    if (comparison.length && identityKey(comparison[0]) !== identityKey(item)) { setError('Escolha execuções da mesma obra, compositor e arranjador.'); return; }
    setError(''); setSelected(current => [...current, item.id]);
  }

  return <section className="workspace-panel">
    <h2>Execuções, favoritos e anotações</h2>
    <p>Compare versões da mesma obra com os mesmos créditos. As anotações ficam no seu acervo e não alteram o vídeo no YouTube.</p>
    {!channelId && <p>Selecione um canal conectado para consultar as execuções.</p>}
    {loading && <p role="status">Carregando as execuções…</p>}
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    <div className="acervo-form">
      <label>Obra para comparação<select value={group} onChange={event => { setGroup(event.target.value); setSelected([]); setOpened([]); }} disabled={loading || !channelId}>
        <option value="">Todas as execuções</option>
        {groups.map(([key, videos]) => <option key={key} value={key}>{videos[0].work} — {videos[0].composer}{videos[0].arranger ? ` — Arr. ${videos[0].arranger}` : ''} ({videos.length} execuções)</option>)}
      </select></label>
      <label>Pesquisar<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Obra, compositor ou filarmônica" /></label>
      <label><input type="checkbox" checked={onlyFavorites} onChange={event => setOnlyFavorites(event.target.checked)} />Mostrar apenas favoritos</label>
    </div>
    {comparison.length > 0 && <>
      <div className="acervo-actions"><strong>{comparison.length} {comparison.length > 1 ? 'execuções selecionadas' : 'execução selecionada'}</strong><button onClick={() => { setSelected([]); setOpened([]); }}>Limpar comparação</button></div>
      {comparison.length === 1 && <p>Selecione outra execução da mesma obra para comparar lado a lado.</p>}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 280px), 1fr))', gap: 16 }}>
        {comparison.map(item => <article className="acervo-record" key={item.id}>
          <h3>{item.title}</h3>
          <dl><dt>Apresentação</dt><dd>{item.events.length ? item.events.map((event, index) => <div key={index}>{event.name || 'Evento sem nome'} — {dateLabel(event.performed_at)}{event.venue ? ` — ${event.venue}` : ''}</div>) : 'Data não cadastrada'}</dd>
            <dt>Publicado no YouTube</dt><dd>{dateLabel(item.published_at)}</dd>
            <dt>Filarmônica</dt><dd>{item.ensemble || item.events.find(event => event.ensemble)?.ensemble || 'Não identificada'}</dd>
            <dt>Compositor</dt><dd>{item.composer || 'Não identificado'}</dd>
            <dt>Arranjador</dt><dd>{item.arranger || 'Não informado'}</dd>
            <dt>Gênero</dt><dd>{item.genre || 'Não informado'}</dd></dl>
          <div className="acervo-actions"><a href={`https://www.youtube.com/watch?v=${encodeURIComponent(item.id)}`} target="_blank" rel="noreferrer">Abrir no YouTube</a><button onClick={() => setOpened(current => current.includes(item.id) ? current.filter(id => id !== item.id) : [...current, item.id])}>{opened.includes(item.id) ? 'Fechar player' : 'Abrir player'}</button></div>
          {opened.includes(item.id) && <iframe title={item.title} src={`https://www.youtube-nocookie.com/embed/${encodeURIComponent(item.id)}`} loading="lazy" allow="encrypted-media; picture-in-picture" allowFullScreen style={{ width: '100%', aspectRatio: '16 / 9', border: 0 }} />}
          <details><summary>Descrição publicada</summary><pre>{item.description || 'Sem descrição.'}</pre></details>
        </article>)}
      </div>
    </>}
    <div className="acervo-record-list" style={{ marginTop: 24 }}>
      {!loading && channelId && candidates.length === 0 && <p>Nenhuma execução encontrada com esses filtros.</p>}
      {candidates.map(item => {
        const record = favoriteMap.get(item.id); const favorite = record?.payload.favorite === true;
        return <article className="acervo-record" key={item.id}>
          <h3>{item.title}</h3><small>{item.composer || 'Compositor não identificado'}{item.arranger ? ` · Arr. ${item.arranger}` : ''} · Publicação: {dateLabel(item.published_at)}</small>
          <div className="acervo-actions"><button aria-pressed={selected.includes(item.id)} onClick={() => toggleComparison(item)}>{selected.includes(item.id) ? 'Retirar da comparação' : 'Comparar execução'}</button>
            <button aria-pressed={favorite} disabled={!!saving} onClick={() => void save(item, !favorite)}>{favorite ? '★ Favorito' : '☆ Marcar favorito'}</button>
            <a href={`https://www.youtube.com/watch?v=${encodeURIComponent(item.id)}`} target="_blank" rel="noreferrer">YouTube</a></div>
          <label>Anotação sobre esta execução<textarea value={drafts[item.id] ?? record?.payload.notes ?? ''} onChange={event => setDrafts(current => ({ ...current, [item.id]: event.target.value }))} placeholder="O que distingue esta execução?" /></label>
          <div className="acervo-actions"><button disabled={!!saving || (drafts[item.id] ?? record?.payload.notes ?? '') === (record?.payload.notes ?? '')} onClick={() => void save(item, favorite)}>{saving === item.id ? 'Salvando…' : 'Salvar anotação'}</button></div>
        </article>;
      })}
    </div>
  </section>;
}
