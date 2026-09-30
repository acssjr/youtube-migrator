import { useEffect, useState } from 'react';
import { acervoApi, AcervoRecord } from '../services/acervoApi';
export interface RecordField { key: string; label: string; type?: 'text' | 'textarea' | 'date' | 'select' | 'number'; required?: boolean; options?: { value: string; label: string }[] }
export function RecordWorkspace({ kind, title, description, fields, onSaved }: { kind: string; title: string; description: string; fields: RecordField[]; onSaved?: () => void }) {
  const [records, setRecords] = useState<AcervoRecord[]>([]);
  const [draft, setDraft] = useState<Record<string, any>>({});
  const [editing, setEditing] = useState<AcervoRecord>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const load = () => acervoApi.records(kind).then(setRecords).catch(e => setError(String(e)));
  useEffect(() => { setDraft({}); setEditing(undefined); load(); }, [kind]);
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      if (editing) await acervoApi.update(editing.id, draft, editing.updated_at);
      else await acervoApi.create(kind, draft);
      setDraft({}); setEditing(undefined); await load(); onSaved?.();
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  };
  return <section className="workspace-panel"><h2>{title}</h2><p>{description}</p>{error && <p role="alert" className="error-note">{error}</p>}
    <form onSubmit={save}><div className="acervo-form">{fields.map(field => <label className={field.type === 'textarea' ? 'full' : ''} key={field.key}>{field.label}{field.type === 'textarea' ? <textarea disabled={busy} required={field.required} value={draft[field.key] || ''} onChange={e => setDraft({ ...draft, [field.key]: e.target.value })}/> : field.type === 'select' ? <select disabled={busy} required={field.required} value={draft[field.key] || ''} onChange={e => setDraft({ ...draft, [field.key]: e.target.value })}><option value="">Selecione</option>{field.options?.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select> : <input disabled={busy} required={field.required} type={field.type || 'text'} value={draft[field.key] ?? ''} onChange={e => setDraft({ ...draft, [field.key]: field.type === 'number' ? Number(e.target.value) : e.target.value })}/>}</label>)}</div><div className="acervo-actions"><button disabled={busy} type="submit">{busy ? 'Salvando...' : editing ? 'Salvar alterações' : 'Cadastrar'}</button>{editing && <button type="button" disabled={busy} onClick={() => { setEditing(undefined); setDraft({}); }}>Cancelar edição</button>}</div></form>
    <div className="acervo-record-list">{!records.length && <p>Nenhum registro cadastrado.</p>}{records.map(record => <article className="acervo-record" key={record.id}><strong>{record.payload.name || record.payload.title || record.payload.work || record.id}</strong>{fields.filter(field => record.payload[field.key]).map(field => <p key={field.key}><small>{field.label}</small><br/>{String(record.payload[field.key])}</p>)}<div className="acervo-actions"><button disabled={busy} onClick={() => { setEditing(record); setDraft(record.payload); }}>Editar</button><button disabled={busy} onClick={async () => { if (!window.confirm('Remover este registro do catálogo? As versões anteriores ficam preservadas.')) return; setBusy(true); try { await acervoApi.remove(record.id); await load(); } catch(e) { setError(String(e)); } finally { setBusy(false); } }}>Remover</button></div></article>)}</div>
  </section>;
}
