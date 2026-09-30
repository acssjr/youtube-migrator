import { FormEvent, useEffect, useMemo, useState } from 'react';
import { acervoApi, AcervoRecord } from '../services/acervoApi';
import './AcervoForms.css';

interface EventData {
  name: string; project: string; night: string; performed_at: string;
  ensemble: string; venue: string; playlist_url: string; video_ids: string[]; notes: string;
}
const blank: EventData = { name: '', project: '', night: '', performed_at: '', ensemble: '', venue: '', playlist_url: '', video_ids: [], notes: '' };
const normalize = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
function videoIds(input: string): string[] {
  return [...new Set(input.split(/[\s,;]+/).filter(Boolean).map(value => {
    if (/^[\w-]{11}$/.test(value)) return value;
    try {
      const url = new URL(value);
      if (url.hostname === 'youtu.be') return url.pathname.slice(1).split('/')[0];
      if (['youtube.com', 'www.youtube.com', 'm.youtube.com'].includes(url.hostname)) return url.searchParams.get('v') || url.pathname.match(/^\/(?:shorts|live|embed)\/([\w-]{11})/)?.[1] || '';
    } catch { /* Invalid input is reported before saving. */ }
    return '';
  }))];
}
function playlistLink(value: string): string {
  if (!value.trim()) return '';
  const url = new URL(value.trim());
  if (!['youtube.com', 'www.youtube.com', 'm.youtube.com'].includes(url.hostname) || !['https:', 'http:'].includes(url.protocol) || !url.searchParams.get('list')) throw new Error('Informe um link de playlist do YouTube válido.');
  return `https://www.youtube.com/playlist?list=${encodeURIComponent(url.searchParams.get('list')!)}`;
}

export function EventCatalog() {
  const [records, setRecords] = useState<AcervoRecord<EventData>[]>([]);
  const [draft, setDraft] = useState<EventData>({ ...blank });
  const [videoInput, setVideoInput] = useState('');
  const [editing, setEditing] = useState<AcervoRecord<EventData>>();
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [removing, setRemoving] = useState<string>();
  const load = () => acervoApi.records<EventData>('event').then(setRecords);
  useEffect(() => { let active = true; acervoApi.records<EventData>('event').then(items => { if (active) setRecords(items); }).catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);
  const filtered = useMemo(() => records.filter(record => normalize([record.payload.name, record.payload.project, record.payload.night, record.payload.ensemble, record.payload.venue, record.payload.performed_at, record.payload.notes].join(' ')).includes(normalize(query))).sort((a, b) => (b.payload.performed_at || '').localeCompare(a.payload.performed_at || '') || a.payload.name.localeCompare(b.payload.name)), [records, query]);
  const reset = () => { setDraft({ ...blank }); setVideoInput(''); setEditing(undefined); };
  const change = (key: keyof EventData, value: string) => setDraft(previous => ({ ...previous, [key]: value }));
  const save = async (event: FormEvent) => {
    event.preventDefault(); setError(''); setNotice(''); setBusy(true);
    try {
      const ids = videoIds(videoInput);
      if (ids.some(id => !/^[\w-]{11}$/.test(id))) throw new Error('Confira os vídeos: use IDs com 11 caracteres ou links individuais do YouTube.');
      const payload = { ...draft, name: draft.name.trim(), video_ids: ids, playlist_url: playlistLink(draft.playlist_url) };
      if (!payload.name) throw new Error('Informe o nome da apresentação.');
      if (editing) await acervoApi.update(editing.id, payload, editing.updated_at);
      else await acervoApi.create('event', payload);
      await load(); reset(); setNotice('Apresentação salva no catálogo.');
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };
  const remove = async (id: string) => {
    setBusy(true); setError(''); setNotice('');
    try { await acervoApi.remove(id); await load(); if (editing?.id === id) reset(); setRemoving(undefined); setNotice('Registro removido do catálogo.'); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };
  return <section className="workspace-panel">
    <h2>Apresentações e eventos</h2>
    <p>Registre cada noite, sua filarmônica e os vídeos correspondentes. A data da apresentação é independente da data em que os vídeos foram publicados.</p>
    {error && <p role="alert" className="error-note">{error}</p>}{notice && <p role="status">{notice}</p>}
    <form onSubmit={save}>
      <div className="acervo-form">
        <label>Nome da apresentação<input required maxLength={300} disabled={busy} value={draft.name} onChange={e => change('name', e.target.value)} placeholder="Ex.: Retreta — 5ª Noite"/></label>
        <label>Projeto<input disabled={busy} value={draft.project} onChange={e => change('project', e.target.value)} placeholder="Ex.: Retreta"/></label>
        <label>Noite ou edição<input disabled={busy} value={draft.night} onChange={e => change('night', e.target.value)} placeholder="Ex.: 5ª Noite"/></label>
        <label>Data da apresentação<input type="date" disabled={busy} value={draft.performed_at} onChange={e => change('performed_at', e.target.value)}/></label>
        <label>Filarmônica<input disabled={busy} value={draft.ensemble} onChange={e => change('ensemble', e.target.value)}/></label>
        <label>Local<input disabled={busy} value={draft.venue} onChange={e => change('venue', e.target.value)}/></label>
        <label className="full">Playlist do YouTube<input type="url" disabled={busy} value={draft.playlist_url} onChange={e => change('playlist_url', e.target.value)} placeholder="https://www.youtube.com/playlist?list=…"/></label>
        <label className="full">Vídeos da apresentação<textarea disabled={busy} value={videoInput} onChange={e => setVideoInput(e.target.value)} placeholder="Cole os links ou IDs dos vídeos, um por linha."/><small>Vídeos repetidos serão registrados uma única vez. Salvar este catálogo não altera o YouTube.</small></label>
        <label className="full">Observações<textarea disabled={busy} value={draft.notes} onChange={e => change('notes', e.target.value)}/></label>
      </div>
      <div className="acervo-actions"><button disabled={busy} type="submit">{busy ? 'Salvando…' : editing ? 'Salvar alterações' : 'Cadastrar apresentação'}</button>{editing && <button type="button" disabled={busy} onClick={reset}>Cancelar edição</button>}</div>
    </form>
    <label>Buscar apresentações<input className="acervo-search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Projeto, noite, filarmônica, local ou data"/></label>
    <p>{loading ? 'Carregando apresentações…' : `${filtered.length} ${filtered.length === 1 ? 'apresentação' : 'apresentações'}`}</p>
    <div className="acervo-record-list">{!loading && !filtered.length && <p>{records.length ? 'Nenhuma apresentação corresponde à busca.' : 'Nenhuma apresentação cadastrada.'}</p>}{filtered.map(record => {
      const data = record.payload;
      let safePlaylist = ''; try { safePlaylist = playlistLink(data.playlist_url || ''); } catch { /* Imported records may contain malformed links. */ }
      return <article className="acervo-record" key={record.id}><strong>{data.name}</strong><p>{[data.project, data.night, data.ensemble].filter(Boolean).join(' · ')}</p>
        {data.performed_at && <p><small>Data da apresentação</small><br/>{/^\d{4}-\d{2}-\d{2}$/.test(data.performed_at) ? data.performed_at.split('-').reverse().join('/') : data.performed_at}</p>}
        {data.venue && <p><small>Local</small><br/>{data.venue}</p>}{safePlaylist && <p><a href={safePlaylist} target="_blank" rel="noreferrer">Abrir playlist no YouTube</a></p>}
        <p>{(data.video_ids || []).length} vídeo(s) vinculado(s)</p>
        {!!data.video_ids?.length && <details><summary>Ver vídeos</summary><ul>{data.video_ids.map(id => <li key={id}><a href={`https://www.youtube.com/watch?v=${encodeURIComponent(id)}`} target="_blank" rel="noreferrer">{id}</a></li>)}</ul></details>}
        {data.notes && <pre>{data.notes}</pre>}
        <div className="acervo-actions"><button disabled={busy} onClick={() => { setEditing(record); setDraft({ ...blank, ...data }); setVideoInput((data.video_ids || []).join('\n')); setError(''); setNotice(''); setRemoving(undefined); }}>Editar</button><button disabled={busy} onClick={() => setRemoving(record.id)}>Remover</button></div>
        {removing === record.id && <div role="group" aria-label="Confirmar remoção"><p>Remover “{data.name}” do catálogo? A playlist e os vídeos no YouTube continuarão disponíveis.</p><div className="acervo-actions"><button disabled={busy} onClick={() => remove(record.id)}>Confirmar remoção</button><button disabled={busy} onClick={() => setRemoving(undefined)}>Cancelar</button></div></div>}
      </article>;
    })}</div>
  </section>;
}
