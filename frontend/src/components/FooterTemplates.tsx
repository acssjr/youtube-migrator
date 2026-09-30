import { useEffect, useState } from 'react';

interface Stored { id: string; payload: { name?: string; ensemble?: string; project?: string; text?: string }; updated_at: string; created_at?: string }
interface Video { id: string; title: string }
interface Comparison { revision_id: string; video_id: string; title: string; before: string; after: string; warning: string }
async function call<T>(path: string, body?: unknown, method = 'POST'): Promise<T> {
  const response = await fetch(`/api${path}`, { method: body === undefined ? 'GET' : method, headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível concluir a operação.');
  return data;
}

export function FooterTemplates({ channelId }: { channelId: string }) {
  const [records, setRecords] = useState<Stored[]>([]);
  const [selected, setSelected] = useState('');
  const [versions, setVersions] = useState<Stored[]>([]);
  const [version, setVersion] = useState('');
  const [name, setName] = useState('');
  const [ensemble, setEnsemble] = useState('');
  const [project, setProject] = useState('');
  const [text, setText] = useState('');
  const [videos, setVideos] = useState<Video[]>([]);
  const [ids, setIds] = useState<string[]>([]);
  const [filter, setFilter] = useState('');
  const [comparisons, setComparisons] = useState<Comparison[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const refresh = async () => setRecords(await call<Stored[]>('/acervo/records?kind=footer'));
  useEffect(() => { refresh().catch(error => setMessage(String(error))); }, []);
  useEffect(() => { setVideos([]); setIds([]); setComparisons([]); setVersions([]); }, [channelId]);
  const run = async (action: () => Promise<void>) => { setBusy(true); setMessage(''); try { await action(); } catch (error) { setMessage(String(error)); } finally { setBusy(false); } };
  const choose = (id: string) => {
    setSelected(id); setVersion(''); setComparisons([]);
    const value = records.find(record => record.id === id)?.payload || {};
    setName(value.name || ''); setEnsemble(value.ensemble || ''); setProject(value.project || ''); setText(value.text || '');
    setVersions([]);
    if (id) call<Stored[]>(`/acervo/records/${id}/versions`).then(setVersions).catch(error => setMessage(String(error)));
  };
  const change = (setter: (value: string) => void, value: string) => { setter(value); setComparisons([]); };
  const save = () => run(async () => {
    const payload = { name, ensemble, project, text };
    const current = records.find(record => record.id === selected);
    const record = await call<Stored>(selected ? `/acervo/records/${selected}` : '/acervo/records', selected ? { payload, expected_updated_at: current?.updated_at } : { kind: 'footer', payload }, selected ? 'PATCH' : 'POST');
    await refresh(); setSelected(record.id); setVersion(''); setComparisons([]); setVersions(await call<Stored[]>(`/acervo/records/${record.id}/versions`)); setMessage('Rodapé salvo. A versão anterior foi preservada.');
  });
  const preview = () => run(async () => {
    const result: Comparison[] = [];
    for (let offset = 0; offset < ids.length; offset += 50) result.push(...await call<Comparison[]>('/footer-templates/preview', { channel_id: channelId, record_id: selected, version_id: version || null, video_ids: ids.slice(offset, offset + 50) }));
    setComparisons(result);
  });
  const publish = () => run(async () => {
    let applied = 0, failed = 0;
    for (let offset = 0; offset < comparisons.length; offset += 50) {
      const result = await call<{ status: string }[]>('/revisions/apply', { channel_id: channelId, revision_ids: comparisons.slice(offset, offset + 50).map(item => item.revision_id) });
      applied += result.filter(item => item.status === 'applied').length; failed += result.filter(item => item.status !== 'applied').length;
    }
    setComparisons([]); setMessage(`${applied} descrições publicadas. ${failed ? `${failed} falharam; confira o histórico antes de repetir.` : 'Versões anteriores disponíveis no histórico para restauração.'}`);
  });
  const visible = videos.filter(video => video.title.toLocaleLowerCase().includes(filter.toLocaleLowerCase()));
  const current = records.find(record => record.id === selected)?.payload;
  const dirty = selected && !version && (name !== (current?.name || '') || ensemble !== (current?.ensemble || '') || project !== (current?.project || '') || text !== (current?.text || ''));
  return <section className="workspace-panel">
    <h2>Rodapés e links do acervo</h2>
    <p>Guarde os links por projeto e filarmônica. O texto “SIGA”, as biografias e as curiosidades existentes são preservados.</p>
    <label>Modelo<select value={selected} disabled={busy} onChange={event => choose(event.target.value)}><option value="">Novo rodapé</option>{records.map(record => <option key={record.id} value={record.id}>{record.payload.name || 'Sem nome'} · {record.payload.ensemble || 'Universal'}</option>)}</select></label>
    <label>Nome<input value={name} disabled={busy || !!version} onChange={event => change(setName, event.target.value)} /></label>
    <label>Filarmônica (opcional)<input value={ensemble} disabled={busy || !!version} onChange={event => change(setEnsemble, event.target.value)} /></label>
    <label>Projeto<input value={project} disabled={busy || !!version} onChange={event => change(setProject, event.target.value)} /></label>
    <label>Rodapé com os links<textarea rows={10} maxLength={5000} value={text} disabled={busy || !!version} onChange={event => change(setText, event.target.value)} /></label>
    <p>Inclua apenas os blocos de playlists. Se não houver um bloco reconhecido no vídeo, o modelo será acrescentado ao final, sem apagar o texto atual.</p>
    <button type="button" disabled={busy || !name.trim() || !text.trim() || !!version} onClick={save}>Salvar versão</button>
    {!!versions.length && <label>Versão para aplicar<select disabled={busy} value={version} onChange={event => { const id = event.target.value; setVersion(id); setComparisons([]); const value = (id ? versions.find(item => item.id === id) : records.find(item => item.id === selected))?.payload; setName(value?.name || ''); setEnsemble(value?.ensemble || ''); setProject(value?.project || ''); setText(value?.text || ''); }}><option value="">Atual</option>{versions.map(item => <option value={item.id} key={item.id}>{new Date(item.created_at || item.updated_at).toLocaleString('pt-BR')}</option>)}</select></label>}
    <hr />
    <button type="button" disabled={busy || !channelId} onClick={() => run(async () => { setVideos(await call<Video[]>(`/revisions/${encodeURIComponent(channelId)}/videos`)); setIds([]); setComparisons([]); })}>Carregar vídeos do canal</button>
    {!!videos.length && <><label>Filtrar títulos<input value={filter} disabled={busy} onChange={event => setFilter(event.target.value)} /></label><button type="button" disabled={busy} onClick={() => { setIds([...new Set([...ids, ...visible.map(video => video.id)])]); setComparisons([]); }}>Selecionar resultados</button><button type="button" disabled={busy} onClick={() => { setIds([]); setComparisons([]); }}>Limpar seleção</button><div style={{ maxHeight: 320, overflow: 'auto' }}>{visible.map(video => <label key={video.id} style={{ display: 'flex', gap: 12, alignItems: 'center' }}><input type="checkbox" disabled={busy} checked={ids.includes(video.id)} onChange={event => { setIds(event.target.checked ? [...ids, video.id] : ids.filter(id => id !== video.id)); setComparisons([]); }} />{video.title}</label>)}</div></>}
    <p>{ids.length} vídeos selecionados{dirty ? ' · Salve as alterações do modelo antes de gerar a prévia.' : ''}</p>
    <button type="button" disabled={busy || !selected || !ids.length || !!dirty} onClick={preview}>Conferir antes e depois</button>
    {comparisons.map(item => <details key={item.revision_id}><summary>{item.title}</summary><p>{item.warning}</p><h3>Antes</h3><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{item.before}</pre><h3>Depois</h3><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{item.after}</pre></details>)}
    {!!comparisons.length && <button type="button" disabled={busy} onClick={publish}>Publicar {comparisons.length} descrições revisadas</button>}
    {busy && <p role="status">Processando…</p>}{message && <p role="status">{message}</p>}
  </section>;
}
