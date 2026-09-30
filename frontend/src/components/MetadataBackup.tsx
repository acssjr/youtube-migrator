import { acervoApi } from '../services/acervoApi';
import { useEffect, useState } from 'react';
import { api } from '../services/api';
import './AcervoForms.css';

type Summary = { imported: boolean; new_records: number; duplicate_records: number; historical_versions: number; youtube_changes: number };
export default function MetadataBackup({ channelId }: { channelId?: string }) {
  const [accounts, setAccounts] = useState<{ channel_id: string; channel_title: string }[]>([]);
  const [channel, setChannel] = useState(channelId || '');
  const [archive, setArchive] = useState<Record<string, unknown>>();
  const [summary, setSummary] = useState<Summary>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { if (channelId !== undefined) setChannel(channelId); }, [channelId]);
  useEffect(() => { if (channelId === undefined) api.auth.getAccounts().then(items => { setAccounts(items); setChannel(items[0]?.channel_id || ''); }).catch(e => setError(String(e))); }, [channelId]);
  const run = async (operation: () => Promise<void>) => { setBusy(true); setError(''); try { await operation(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); } };
  const download = (format: 'export' | 'csv') => run(async () => {
    const response = await fetch(`/api/archive-backup/${format}${channel ? `?channel_id=${encodeURIComponent(channel)}` : ''}`);
    if (!response.ok) { const detail = await response.json(); throw new Error(typeof detail.detail === 'string' ? detail.detail : 'Não foi possível gerar o backup.'); }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a'); link.href = url; link.download = format === 'csv' ? 'acervo-metadados.csv' : 'acervo-metadados.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    await acervoApi.create('backup', {name:'Metadados preparados em ' + (format === 'csv' ? 'CSV' : 'JSON'),channel_id:channel,format,delivery:'requested',prepared_at:new Date().toISOString()}).catch(() => setError('O arquivo foi preparado, mas não foi possível registrar este backup no histórico.'));

  });
  const inspect = async (candidate: Record<string, unknown>, confirm = false) => {
    const portable = {format:candidate.format,version:candidate.version,records:candidate.records || [],record_versions:candidate.record_versions || []};
    const requestBytes = new TextEncoder().encode(JSON.stringify(portable)).length;
    if (requestBytes > 4 * 1024 * 1024) throw new Error('Os registros deste backup excedem o limite de importação de 4 MB. Divida os registros em arquivos menores. Vídeos e playlists não contam nesse limite.');
    const response = await fetch('/api/archive-backup/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ archive: portable, confirm }) });
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Backup inválido. Escolha um JSON exportado pelo Acervo.');
    setSummary(result); if (confirm) setArchive(undefined);
  };
  return <section className="workspace-panel acervo-tools">
    <h2>Backup dos metadados</h2>
    <p>Guarde os títulos e descrições publicados, playlists com a ordem dos vídeos, seus registros, versões de textos e o histórico de alterações das descrições. O JSON permite recuperar os registros do acervo. Os arquivos de vídeo são baixados pela ferramenta de downloads.</p>
    {channelId === undefined && <label>Canal<select value={channel} disabled={busy} onChange={e => setChannel(e.target.value)}><option value="">Somente os registros do acervo</option>{accounts.map(account => <option key={account.channel_id} value={account.channel_id}>{account.channel_title}</option>)}</select></label>}
    <div className="acervo-actions"><button type="button" disabled={busy} onClick={() => download('export')}>Baixar backup completo em JSON</button><button type="button" disabled={busy || !channel} onClick={() => download('csv')}>Baixar planilha de vídeos</button></div>
    <h3>Recuperar registros</h3>
    <p>A importação acrescenta registros e histórico do acervo, preserva os dados atuais e ignora duplicatas exatas. Títulos, descrições, playlists e revisões do YouTube ficam disponíveis no arquivo para consulta; esta operação não os publica.</p>
    <label>Escolher backup JSON<input type="file" accept=".json,application/json" disabled={busy} onChange={event => { const file = event.target.files?.[0]; setArchive(undefined); setSummary(undefined); if (!file) return; run(async () => { if (file.size > 20 * 1024 * 1024) throw new Error('O arquivo excede 20 MB.'); const candidate = JSON.parse(await file.text()); await inspect(candidate); setArchive(candidate); }); event.target.value = ''; }} /></label>
    {summary && <div role="status"><p>{summary.imported ? 'Importação concluída.' : 'Prévia da importação:'} {summary.new_records} registros novos, {summary.duplicate_records} duplicatas ignoradas e {summary.historical_versions} versões históricas.</p>{archive && !summary.imported && <button type="button" disabled={busy} onClick={() => run(() => inspect(archive, true))}>Confirmar importação dos registros</button>}</div>}
    {busy && <p role="status">Preparando os metadados…</p>}{error && <p role="alert">{error}</p>}
  </section>;
}
