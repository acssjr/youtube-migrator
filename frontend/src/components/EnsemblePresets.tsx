import { useEffect, useState } from 'react';
import { Check, Plus, Save, Trash2 } from 'lucide-react';
import { acervoApi } from '../services/acervoApi';
import './ensemblePresets.css';

export interface EnsemblePresetPayload {
  name: string;
  socialLinks: string;
  institutionalText: string;
  privacy: 'public' | 'unlisted' | 'private';
  titlePreferences: {
    separator: '—' | '–' | '|';
    includeGenre: boolean;
    includeComposer: boolean;
    includeArranger: boolean;
    includeEnsemble: boolean;
  };
}
interface PresetRecord { id: string; payload: EnsemblePresetPayload; updated_at?: string }
interface Props { onApply?: (payload: Record<string, any>) => void }
const emptyPreset = (): EnsemblePresetPayload => ({
  name: '', socialLinks: '', institutionalText: '', privacy: 'public',
  titlePreferences: { separator: '—', includeGenre: true, includeComposer: true, includeArranger: true, includeEnsemble: true },
});
function normalize(payload: Partial<EnsemblePresetPayload>): EnsemblePresetPayload {
  const initial = emptyPreset();
  return { ...initial, ...payload, titlePreferences: { ...initial.titlePreferences, ...payload.titlePreferences } };
}

export function EnsemblePresets({ onApply }: Props) {
  const [records, setRecords] = useState<PresetRecord[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [draft, setDraft] = useState<EnsemblePresetPayload>(emptyPreset);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [deleteReady, setDeleteReady] = useState(false);
  useEffect(() => {
    let active = true;
    acervoApi.records('ensemble_preset').then(data => {
      if (active) setRecords(data.map(record => ({ ...record, payload: normalize(record.payload) })));
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : 'Não foi possível carregar as filarmônicas.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  const select = (id: string) => {
    setSelectedId(id);
    setDraft(id ? normalize(records.find(record => record.id === id)?.payload || {}) : emptyPreset());
    setDeleteReady(false); setError(''); setNotice('');
  };
  const change = (patch: Partial<EnsemblePresetPayload>) => { setDraft(current => ({ ...current, ...patch })); setNotice(''); setDeleteReady(false); };
  const save = async () => {
    if (saving) return;
    const payload = { ...draft, name: draft.name.trim() };
    if (!payload.name) { setError('Preencha o nome oficial da filarmônica.'); return; }
    if (records.some(record => record.id !== selectedId && record.payload.name.trim().localeCompare(payload.name, 'pt-BR', { sensitivity: 'base' }) === 0)) {
      setError('Essa filarmônica já está cadastrada. Selecione-a para editar.'); return;
    }
    setSaving(true); setError(''); setNotice('');
    try {
      const record = selectedId ? await acervoApi.update(selectedId, payload) : await acervoApi.create('ensemble_preset', payload);
      const saved = { ...record, payload: normalize(record.payload) };
      setRecords(current => [...current.filter(item => item.id !== saved.id), saved]);
      setSelectedId(saved.id); setDraft(saved.payload); setNotice('Filarmônica salva. Seus textos foram preservados.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Não foi possível salvar.'); }
    finally { setSaving(false); }
  };
  const remove = async () => {
    if (!selectedId || saving) return;
    if (!deleteReady) { setDeleteReady(true); return; }
    setSaving(true); setError('');
    try { await acervoApi.remove(selectedId); setRecords(current => current.filter(item => item.id !== selectedId)); select(''); setNotice('Cadastro removido. Os vídeos publicados não foram alterados.'); }
    catch (e) { setError(e instanceof Error ? e.message : 'Não foi possível remover.'); }
    finally { setSaving(false); }
  };
  const preferences = draft.titlePreferences;
  const preview = [preferences.includeGenre ? 'Dobrado Nome da obra' : 'Nome da obra', preferences.includeComposer ? 'Compositor' : '', preferences.includeArranger ? 'Arr. Arranjador' : '', preferences.includeEnsemble ? draft.name.trim() || 'Filarmônica' : ''].filter(Boolean).join(` ${preferences.separator} `);
  return <section className="workspace-panel ensemble-presets" aria-label="Cadastros de filarmônicas">
    <div className="ensemble-presets-heading"><div><h2>Suas filarmônicas</h2><p>Guarde o nome oficial, seus textos e o formato dos títulos para usar nos próximos lotes.</p></div><button type="button" className="secondary-action" disabled={saving || loading} onClick={() => select('')}><Plus size={16}/> Novo cadastro</button></div>
    {loading ? <p role="status">Carregando filarmônicas…</p> : <>
      <label className="ensemble-presets-field">Filarmônica cadastrada<select value={selectedId} disabled={saving} onChange={event => select(event.target.value)}><option value="">Novo cadastro</option>{[...records].sort((a, b) => a.payload.name.localeCompare(b.payload.name, 'pt-BR')).map(record => <option key={record.id} value={record.id}>{record.payload.name}</option>)}</select></label>
      <form onSubmit={event => { event.preventDefault(); void save(); }}>
        <fieldset disabled={saving} className="ensemble-presets-fields"><label className="ensemble-presets-field">Nome oficial<input value={draft.name} maxLength={200} required onChange={event => change({ name: event.target.value })} placeholder="Sociedade Filarmônica…"/></label>
          <label className="ensemble-presets-field">Redes sociais e links<textarea rows={3} maxLength={6000} value={draft.socialLinks} onChange={event => change({ socialLinks: event.target.value })} placeholder="Cole os links e chamadas exatamente como deseja usar."/><small>Este texto será mantido como você escreveu.</small></label>
          <label className="ensemble-presets-field">Texto institucional<textarea rows={5} maxLength={20000} value={draft.institutionalText} onChange={event => change({ institutionalText: event.target.value })} placeholder="Cole o texto aprovado sobre a filarmônica."/></label>
          <div className="ensemble-presets-row"><label className="ensemble-presets-field">Separador do título<select value={preferences.separator} onChange={event => change({ titlePreferences: { ...preferences, separator: event.target.value as EnsemblePresetPayload['titlePreferences']['separator'] } })}><option value="—">Travessão —</option><option value="–">Traço –</option><option value="|">Barra |</option></select></label><label className="ensemble-presets-field">Visibilidade inicial<select value={draft.privacy} onChange={event => change({ privacy: event.target.value as EnsemblePresetPayload['privacy'] })}><option value="public">Público</option><option value="unlisted">Não listado</option><option value="private">Privado</option></select></label></div>
          <div className="ensemble-presets-title-options" role="group" aria-label="Informações no título"><strong>Incluir no título</strong>{([['includeGenre', 'Gênero'], ['includeComposer', 'Compositor'], ['includeArranger', 'Arranjador'], ['includeEnsemble', 'Filarmônica']] as const).map(([key, label]) => <label key={key}><input type="checkbox" checked={preferences[key]} onChange={event => change({ titlePreferences: { ...preferences, [key]: event.target.checked } })}/>{label}</label>)}</div>
          <div className="ensemble-presets-preview"><small>Exemplo do formato · os campos sem informação serão omitidos</small><p>{preview}</p></div>
        </fieldset>
        {error && <p className="ensemble-presets-error" role="alert">{error}</p>}{notice && <p className="ensemble-presets-notice" role="status">{notice}</p>}
        <div className="ensemble-presets-actions"><button type="submit" className="primary-action" disabled={saving || !draft.name.trim()}><Save size={16}/>{saving ? 'Salvando…' : 'Salvar cadastro'}</button>{onApply && <button type="button" className="secondary-action" disabled={saving || !draft.name.trim()} onClick={() => { onApply({ ...draft, name: draft.name.trim() }); setNotice('Preferências aplicadas ao lote. Confira antes de enviar.'); }}><Check size={16}/>Aplicar ao lote</button>}{selectedId && <button type="button" className="ensemble-presets-delete" disabled={saving} onClick={() => void remove()}><Trash2 size={15}/>{deleteReady ? 'Confirmar exclusão do cadastro' : 'Excluir cadastro'}</button>}{deleteReady && <button type="button" className="secondary-action" disabled={saving} onClick={() => setDeleteReady(false)}>Cancelar exclusão</button>}</div>
      </form>
    </>}
  </section>;
}
export default EnsemblePresets;
