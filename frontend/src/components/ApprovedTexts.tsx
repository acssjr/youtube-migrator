import { useEffect, useState } from 'react';
import { acervoApi, AcervoRecord } from '../services/acervoApi';

type Role = 'composer' | 'arranger' | 'work' | 'ensemble';
interface Passage { role: Role; name: string; text: string; source_url: string; approved: boolean }
const roles: Record<Role, string> = { composer: 'Compositor', arranger: 'Arranjador', work: 'Obra', ensemble: 'Filarmônica' };
const blank = (): Passage => ({ role: 'composer', name: '', text: '', source_url: '', approved: true });

export function ApprovedTexts({ channelId }: { channelId?: string }) {
  const [records, setRecords] = useState<AcervoRecord<Passage>[]>([]);
  const [draft, setDraft] = useState<Passage>(blank);
  const [editing, setEditing] = useState<AcervoRecord<Passage>>();
  const [history, setHistory] = useState<AcervoRecord<Passage>[]>([]);
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [importLink, setImportLink] = useState('');
  const [imported, setImported] = useState<{ role: Role; text: string }[]>([]);
  const reload = () => acervoApi.records<Passage>('approved_text').then(setRecords);
  useEffect(() => { reload().catch(error => setNotice(String(error))); }, []);
  const reset = () => { setEditing(undefined); setDraft(blank()); setHistory([]); };
  const save = async () => {
    setBusy(true); setNotice('');
    try {
      if (!draft.name.trim() || !draft.text.trim()) throw new Error('Informe o nome e o texto completo.');
      if (draft.source_url && !/^https?:\/\//i.test(draft.source_url)) throw new Error('Use um link da fonte iniciado por https:// ou http://.');
      const payload = { ...draft, name: draft.name.trim() }; // Text is deliberately preserved byte for byte.
      if (editing) await acervoApi.update(editing.id, payload, editing.updated_at);
      else await acervoApi.create('approved_text', payload);
      await reload(); reset(); setNotice('Texto salvo exatamente como preenchido.');
    } catch (error) { setNotice(String(error)); }
    finally { setBusy(false); }
  };
  const edit = async (record: AcervoRecord<Passage>) => {
    setEditing(record); setDraft({ ...record.payload }); setHistory([]); setNotice('');
    try { setHistory(await acervoApi.versions(record.id) as AcervoRecord<Passage>[]); }
    catch (error) { setNotice(String(error)); }
  };
  const remove = async () => {
    if (!editing || !window.confirm(`Excluir o texto de ${editing.payload.name}?`)) return;
    setBusy(true);
    try { await acervoApi.remove(editing.id); await reload(); reset(); setNotice('Texto excluído.'); }
    catch (error) { setNotice(String(error)); }
    finally { setBusy(false); }
  };
  const filtered = records.filter(record => `${record.payload.name} ${roles[record.payload.role] || ''}`.toLocaleLowerCase('pt-BR').includes(query.toLocaleLowerCase('pt-BR')));
  const importPublished = async () => {
    if (!channelId) return;
    setBusy(true); setNotice(''); setImported([]);
    try {
      const link = new URL(importLink);
      const host = link.hostname.toLowerCase();
      if (!['youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'].includes(host)) throw new Error('Cole o link de um vídeo do YouTube.');
      const videoId = host === 'youtu.be' ? link.pathname.slice(1) : link.searchParams.get('v') || '';
      if (!/^[\w-]{11}$/.test(videoId)) throw new Error('Não foi possível identificar o vídeo no link.');
      const response = await fetch(`/api/approved-texts/${encodeURIComponent(channelId)}/${encodeURIComponent(videoId)}/blocks`);
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível consultar o vídeo.');
      setImported(data.blocks); setDraft(previous => ({ ...previous, source_url: data.source_url }));
      if (!data.blocks.length) setNotice('Não há um bloco identificado por “Sobre o compositor”, “Sobre o arranjador”, “Sobre a obra” ou “Sobre a filarmônica”. Cole o texto original abaixo.');
    } catch (error) { setNotice(String(error)); }
    finally { setBusy(false); }
  };
  return <section className="workspace-panel approved-texts">
    <div className="panel-top"><div><h2>Textos aprovados</h2><p>Guarde seu texto original e a fonte. As descrições reutilizam o conteúdo aprovado sem reescrevê-lo.</p></div></div>
    <div style={{ padding: 20, display: 'grid', gap: 16 }}>
      {channelId && <div style={{ display: 'grid', gap: 8 }}><label>Importar texto publicado no canal<input type="url" value={importLink} onChange={event => setImportLink(event.target.value)} placeholder="Link do vídeo com seu texto original" /></label><button type="button" className="secondary-action" disabled={busy || !importLink} onClick={importPublished}>Consultar os blocos publicados</button>{imported.map((block, index) => <article key={index}><pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{block.text}</pre><button type="button" className="secondary-action" disabled={busy} onClick={() => { setDraft(previous => ({ ...previous, role: block.role, text: block.text, approved: false })); setNotice('Bloco copiado exatamente. Informe o nome, confira e marque como aprovado antes de salvar.'); }}>Usar este bloco de {roles[block.role].toLowerCase()}</button></article>)}</div>}
      <label>Buscar por nome ou tipo<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Compositor, obra, filarmônica…" /></label>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {filtered.map(record => <button type="button" className={editing?.id === record.id ? 'primary-action' : 'secondary-action'} key={record.id} disabled={busy} onClick={() => edit(record)}>{record.payload.name} · {roles[record.payload.role]}{!record.payload.approved && ' · Rascunho'}</button>)}
        <button type="button" className="secondary-action" disabled={busy} onClick={reset}>Novo texto</button>
      </div>
      {!records.length && <p>Nenhum texto cadastrado. Cole o bloco publicado completo, incluindo “Sobre o compositor”, quando houver.</p>}
      <fieldset disabled={busy} style={{ border: 0, padding: 0, display: 'grid', gap: 14 }}>
        <legend>{editing ? 'Editar texto e criar uma versão' : 'Cadastrar texto'}</legend>
        <label>Tipo<select value={draft.role} onChange={event => setDraft({ ...draft, role: event.target.value as Role })}>{Object.entries(roles).map(([role, label]) => <option key={role} value={role}>{label}</option>)}</select></label>
        <label>Nome exato<input value={draft.name} onChange={event => setDraft({ ...draft, name: event.target.value })} maxLength={300} /></label>
        <label>Texto original<textarea value={draft.text} onChange={event => setDraft({ ...draft, text: event.target.value })} rows={10} maxLength={5000} style={{ width: '100%', whiteSpace: 'pre-wrap' }} /></label>
        <label>Link da fonte (opcional)<input type="url" value={draft.source_url} onChange={event => setDraft({ ...draft, source_url: event.target.value })} placeholder="https://www.youtube.com/watch?v=…" /></label>
        <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}><input type="checkbox" style={{ width: 'auto' }} checked={draft.approved} onChange={event => setDraft({ ...draft, approved: event.target.checked })} />Aprovado para reutilizar nas prévias</label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}><button type="button" className="primary-action" onClick={save}>Salvar texto</button>{editing && <button type="button" className="secondary-action" onClick={remove}>Excluir texto</button>}</div>
      </fieldset>
      {notice && <p role="status">{notice}</p>}
      {editing && <details><summary>Versões anteriores ({history.length})</summary>{history.map(version => <article key={version.id} style={{ borderTop: '1px solid #ddd', padding: '12px 0' }}><p>{new Date(version.created_at).toLocaleString('pt-BR')} · {version.payload.name}</p><pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{version.payload.text}</pre><button type="button" className="secondary-action" disabled={busy} onClick={() => { setDraft({ ...version.payload }); setNotice('Versão carregada. Confira e salve para restaurar, mantendo o histórico.'); }}>Usar esta versão</button></article>)}</details>}
    </div>
  </section>;
}
