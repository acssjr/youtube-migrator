import { useEffect, useState } from 'react';
import { RecordWorkspace, RecordField } from './RecordWorkspace';
import { acervoApi } from '../services/acervoApi';
import { api } from '../services/api';
import './AcervoForms.css';

type Suggestion = { name: string; genre: string; composer: string; arranger: string; aliases: string; notes: string; sources: { video_id: string; title: string; url: string }[] };
const fields: RecordField[] = [
  { key: 'name', label: 'Nome da obra', required: true }, { key: 'genre', label: 'Gênero (opcional)' },
  { key: 'composer', label: 'Compositor' }, { key: 'arranger', label: 'Arranjador (opcional)' },
  { key: 'aliases', label: 'Outras grafias / nomes', type: 'textarea' }, { key: 'notes', label: 'Notas do acervo', type: 'textarea' },
];
const keyOf = (item: Record<string, any>) => ['name', 'composer', 'arranger'].map(field => String(item[field] || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\s+/g, ' ').trim()).join('|');

export function WorkCatalog({channelId}: {channelId?:string}) {
  const [accounts, setAccounts] = useState<{ channel_id: string; channel_title: string }[]>([]);
  const [channel, setChannel] = useState('');
  const [drafts, setDrafts] = useState<Suggestion[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => { if (channelId !== undefined) {setChannel(channelId);setDrafts([]);setSelected(new Set());return;} api.auth.getAccounts().then(data => { setAccounts(data); setChannel(data[0]?.channel_id || ''); }).catch(e => setError(String(e))); }, [channelId]);
  const discover = async () => {
    setBusy(true); setError(''); setMessage(''); setDrafts([]); setSelected(new Set());
    try {
      const response = await fetch(`/api/work-catalog/${encodeURIComponent(channel)}/suggestions`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Não foi possível consultar o canal.');
      const existing = new Set((await acervoApi.records('work')).map(record => keyOf(record.payload)));
      const fresh = (data as Suggestion[]).filter(item => !existing.has(keyOf(item)));
      setDrafts(fresh); setMessage(`${fresh.length} sugestões para revisar. Nenhuma obra foi cadastrada automaticamente.`);
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  };
  const save = async () => {
    setBusy(true); setError(''); setMessage(''); let count = 0;
    const completed = new Set<number>();
    try {
      const existing = new Set((await acervoApi.records('work')).map(record => keyOf(record.payload)));
      for (const index of selected) {
        const item = drafts[index];
        if (!item.name.trim()) throw new Error('Preencha o nome de todas as obras selecionadas.');
        if (!existing.has(keyOf(item))) {
          await acervoApi.create('work', { ...item, channel_id: channel }); existing.add(keyOf(item)); count++;
        }
        completed.add(index);
      }
      setMessage(`${count} obras cadastradas. Os vídeos permanecem como estão.`);
    } catch (e) { setError(String(e)); } finally {
      setDrafts(items => items.filter((_, index) => !completed.has(index)));
      setSelected(new Set()); setRevision(value => value + 1); setBusy(false);
    }
  };
  const change = (index: number, field: string, value: string) => setDrafts(items => items.map((item, position) => position === index ? { ...item, [field]: value } : item));
  return <div className="acervo-tools">
    <section className="workspace-panel"><h2>Reconhecer obras do canal</h2><p>Consulte os títulos existentes, confira os créditos e aprove apenas o que estiver correto. Grafias parecidas podem representar obras diferentes.</p>
      {error && <p role="alert" className="error-note">{error}</p>}{message && <p role="status">{message}</p>}
      {channelId === undefined && <label>Canal<select disabled={busy} value={channel} onChange={e => { setChannel(e.target.value); setDrafts([]); setSelected(new Set()); setMessage(''); }}>{accounts.map(account => <option key={account.channel_id} value={account.channel_id}>{account.channel_title}</option>)}</select></label>}
      <div className="acervo-actions"><button disabled={busy || !channel} onClick={discover}>{busy ? 'Aguarde...' : 'Buscar sugestões'}</button>{drafts.length > 0 && <button disabled={busy || !selected.size} onClick={save}>Cadastrar {selected.size} obras revisadas</button>}</div>
      <div className="acervo-record-list">{drafts.map((item, index) => <article className="acervo-record" key={index}>
        <label><input type="checkbox" disabled={busy} checked={selected.has(index)} onChange={e => setSelected(current => { const next = new Set(current); e.target.checked ? next.add(index) : next.delete(index); return next; })}/> Conferi esta obra e seus créditos</label>
        <div className="acervo-form">{fields.map(field => <label key={field.key}>{field.label}<input disabled={busy} value={String(item[field.key as keyof Suggestion] || '')} onChange={e => change(index, field.key, e.target.value)}/></label>)}</div>
        <details><summary>{item.sources.length} gravações de referência</summary>{item.sources.map(source => <p key={source.video_id}><a href={source.url} target="_blank" rel="noreferrer">{source.title}</a></p>)}</details>
      </article>)}</div>
    </section>
    <RecordWorkspace key={revision} kind="work" title="Catálogo de obras" description="Obras e créditos conferidos, com outras grafias e notas. Este cadastro organiza o acervo sem alterar títulos ou descrições do YouTube." fields={fields}/>
  </div>;
}
