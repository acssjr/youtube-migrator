import { ArchiveDashboard } from '../components/ArchiveDashboard';
import MetadataBackup from '../components/MetadataBackup';
import { OriginalArchive } from '../components/OriginalArchive';
import PerformanceCompare from '../components/PerformanceCompare';
import RepertoireHistory from '../components/RepertoireHistory';
import { PlaylistAudit } from '../components/PlaylistAudit';
import SmartPlaylists from '../components/SmartPlaylists';
import { AcervoSearch } from '../components/AcervoSearch';
import { WorkCatalog } from '../components/WorkCatalog';
import { EventCatalog } from '../components/EventCatalog';
import { api } from '../services/api';
import { Account } from '../types';
import { useEffect, useState } from 'react';
import { EnsemblePresets } from '../components/EnsemblePresets';
import { ApprovedTexts } from '../components/ApprovedTexts';
import { FooterTemplates } from '../components/FooterTemplates';
import MetadataRevisions from '../components/MetadataRevisions';
import '../components/AcervoForms.css';

export function AcervoPage({onNavigate}: {onNavigate?:(tab:string)=>void}) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [channelId, setChannelId] = useState('');
  useEffect(() => {api.auth.getAccounts().then(data => {setAccounts(data);setChannelId(data[0]?.channel_id || '');}).catch(() => {});}, []);
  const groups = [
    {id:'explore',label:'Explorar',tools:[{id:'pending',label:'Pendências'},{id:'search',label:'Buscar vídeos'},{id:'repertoire',label:'Repertório'},{id:'compare',label:'Comparar execuções'},{id:'audit',label:'Conferir playlists'}]},
    {id:'organize',label:'Organizar',tools:[{id:'works',label:'Obras'},{id:'events',label:'Apresentações'},{id:'ensembles',label:'Filarmônicas'},{id:'playlists',label:'Criar playlists'}]},
    {id:'texts',label:'Textos e descrições',tools:[{id:'texts',label:'Textos aprovados'},{id:'footers',label:'Rodapés'},{id:'revisions',label:'Histórico de alterações'}]},
    {id:'preserve',label:'Preservar',tools:[{id:'backup',label:'Backup dos metadados'},{id:'originals',label:'Arquivos originais'}]},
  ];
  const [group, setGroup] = useState('explore');
  const [tab, setTab] = useState('pending');
  const active = groups.find(item => item.id === group)!;
  const navigate = (tool:string) => {
    const section = groups.find(item => item.tools.some(t => t.id === tool));
    if (section) {setGroup(section.id);setTab(tool);} else onNavigate?.(tool);
  };
  return <div className="acervo-tools">
    <div className="page-heading"><div><h1>Seu acervo, organizado.</h1><p>Encontre as gravações, prepare os textos e preserve sua história.</p></div></div>
    <label>Canal conectado<select value={channelId} onChange={e => setChannelId(e.target.value)}>{accounts.map(a => <option key={a.id} value={a.channel_id}>{a.channel_title}</option>)}</select></label>
    <nav className="acervo-groups" aria-label="Áreas do acervo">{groups.map(item => <button key={item.id} aria-pressed={group === item.id} onClick={() => {setGroup(item.id);setTab(item.tools[0].id);}}>{item.label}</button>)}</nav>
    <nav className="acervo-tabs" aria-label={`Ferramentas para ${active.label.toLocaleLowerCase()}`}>{active.tools.map(item => <button key={item.id} aria-pressed={tab === item.id} onClick={() => setTab(item.id)}>{item.label}</button>)}</nav>
    {tab === 'pending' && <ArchiveDashboard channelId={channelId} onNavigate={navigate}/>}
    {tab === 'backup' && <MetadataBackup channelId={channelId}/>}
    {tab === 'originals' && <OriginalArchive/>}
    {tab === 'compare' && <PerformanceCompare channelId={channelId}/>}
    {tab === 'repertoire' && <RepertoireHistory channelId={channelId}/>}
    {tab === 'audit' && <PlaylistAudit channelId={channelId}/>}
    {tab === 'playlists' && <SmartPlaylists channelId={channelId}/>}
    {tab === 'search' && <AcervoSearch channelId={channelId}/>}
    {tab === 'works' && <WorkCatalog channelId={channelId}/>}
    {tab === 'events' && <EventCatalog/>}
    {tab === 'texts' && <ApprovedTexts channelId={channelId}/>}
    {tab === 'footers' && <FooterTemplates channelId={channelId}/>}
    {tab === 'ensembles' && <EnsemblePresets/>}
    {tab === 'revisions' && <MetadataRevisions channelId={channelId}/>}
  </div>;
}
