import { formatStoredDate } from '../services/dates';
import { useEffect, useRef, useState } from 'react';
import { acervoApi } from '../services/acervoApi';
import { buildArchivePending, DashboardVideo, PendingSummary } from '../services/archiveDashboard.mjs';

export function ArchiveDashboard({ channelId, onNavigate }: { channelId: string; onNavigate?: (tool: string) => void }) {
  const [summary, setSummary] = useState<PendingSummary>();
  const [count, setCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [checked, setChecked] = useState('');
  const generation = useRef(0);
  useEffect(() => { generation.current++; setSummary(undefined); setCount(0); setChecked(''); setError(''); setBusy(false); return () => { generation.current++; }; }, [channelId]);
  async function refresh() {
    if (!channelId) return;
    const current = ++generation.current;
    setBusy(true); setError('');
    try {
      const [response, records] = await Promise.all([fetch(`/api/acervo-search/${encodeURIComponent(channelId)}`, { cache: 'no-store' }), acervoApi.records()]);
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Não foi possível conferir o canal.');
      if (current !== generation.current) return;
      setSummary(buildArchivePending(data.items, records, channelId)); setCount(data.items.length); setChecked(new Date().toLocaleString('pt-BR'));
    } catch (cause) { if (current === generation.current) setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { if (current === generation.current) setBusy(false); }
  }
  const action = (tool: string, label: string) => onNavigate ? <button type="button" onClick={() => onNavigate(tool)}>{label}</button> : null;
  function videoList(title: string, videos: DashboardVideo[], tool: string, label: string, explanation: string) {
    return <section className="acervo-record"><h3>{title} · {videos.length}</h3><p>{explanation}</p>{!!videos.length && <>{action(tool, label)}<details><summary>Conferir os {videos.length} vídeos</summary><div style={{ maxHeight: 320, overflow: 'auto' }}><ul>{videos.map(video => <li key={video.id}><a href={`https://www.youtube.com/watch?v=${encodeURIComponent(video.id)}`} target="_blank" rel="noreferrer">{video.title || video.id}</a></li>)}</ul></div></details></>}</section>;
  }
  return <section className="workspace-panel">
    <h2>O que precisa de atenção</h2>
    <p>Confira as pendências do canal e escolha por onde continuar. Cada publicação continua passando pela prévia de revisão.</p>
    <div className="acervo-actions"><button type="button" disabled={busy || !channelId} onClick={refresh}>{busy ? 'Conferindo o acervo…' : summary ? 'Atualizar diagnóstico' : 'Conferir meu acervo'}</button>{checked && <small>{count} vídeos conferidos · {checked}</small>}</div>
    {!channelId && <p>Escolha um canal conectado para conferir o acervo.</p>}
    {error && <p role="alert">{error}</p>}
    {summary && <div className="acervo-record-list">
      {videoList('Sem descrição', summary.blank, 'descriptions', 'Preparar descrições', 'Vídeos cuja descrição publicada está vazia.')}
      {videoList('Créditos a conferir', summary.credits, 'search', 'Pesquisar obras e créditos', 'O título e o catálogo não forneceram o nome da obra ou do compositor. Confira o registro antes de usar uma descrição de referência.')}
      {videoList('Obras com referência ambígua', summary.ambiguous, 'search', 'Revisar o catálogo', 'Mais de uma obra cadastrada corresponde ao mesmo vídeo. Nenhuma referência foi escolhida automaticamente.')}
      {videoList('Links de playlists a atualizar', summary.outdated, 'footers', 'Revisar rodapés', 'Faltam links presentes no modelo atual compatível com a filarmônica e o projeto. Confira a prévia para decidir se o modelo se aplica ao vídeo.')}
      <section className="acervo-record"><h3>Apresentações sem data · {summary.undated.length}</h3><p>A data da apresentação deve ser registrada separadamente da data de publicação.</p>{!!summary.undated.length && <>{action('events', 'Completar apresentações')}<ul>{summary.undated.map(record => <li key={record.id}>{record.payload.name || 'Apresentação sem nome'}</li>)}</ul></>}</section>
      {summary.originals ? videoList('Sem original vinculado', summary.originals, 'originals', 'Conferir inventário de originais', 'Estes vídeos ainda não têm um arquivo vinculado pelo ID do YouTube no inventário registrado. Isso não significa que o arquivo foi perdido.') : <section className="acervo-record"><h3>Inventário de originais</h3><p>Cadastre seus arquivos para identificar vídeos sem um original vinculado.</p>{action('originals', 'Registrar originais')}</section>}
      <section className="acervo-record"><h3>Textos e cópias de segurança</h3><p>{summary.approvedCount} textos aprovados · {summary.originalCount} vídeos com original vinculado.</p><p>{summary.latestBackup ? `Último registro de backup: ${formatStoredDate(summary.latestBackup.created_at)} · ${summary.latestBackup.payload.name || 'Cópia do acervo'}.` : 'Nenhuma cópia de segurança registrada no acervo.'}</p><p>O registro informa quando a cópia foi feita; a disponibilidade atual dos arquivos deve ser conferida na pasta de destino.</p><div className="acervo-actions">{action('texts', 'Biblioteca de textos')}{action('backup', 'Backup dos metadados')}{action('originals', 'Backup dos originais')}{action('revisions', 'Histórico de publicações')}</div></section>
    </div>}
  </section>;
}
