import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { ArrowRightLeft, Download, FileText, Settings, Terminal, Youtube } from 'lucide-react';

interface Props { children: React.ReactNode; activeTab: string; setActiveTab: (tab: string) => void }
const items = [
  { id: 'descriptions', label: 'Descrições', icon: FileText, subtitle: 'Organizar o acervo' },
  { id: 'downloads', label: 'Downloads', icon: Download, subtitle: 'Áudio e vídeo' },
  { id: 'migration', label: 'Migração', icon: ArrowRightLeft, subtitle: 'Transferir vídeos' },
  { id: 'settings', label: 'Configurações', icon: Settings, subtitle: 'Canais e preferências' },
  { id: 'logs', label: 'Atividade', icon: Terminal, subtitle: 'Registros do sistema' },
];
export function DashboardLayout({ children, activeTab, setActiveTab }: Props) {
  const [localTools, setLocalTools] = useState(!import.meta.env.PROD);
  useEffect(() => { api.capabilities().then(data => setLocalTools(data.local_tools)).catch(() => {}); }, []);
  const visibleItems = localTools ? items : items.filter(item => ['descriptions', 'downloads', 'settings'].includes(item.id));
  return <div className="app-shell"><aside className="app-sidebar"><div><div className="brand"><span className="brand-icon"><Youtube size={23} strokeWidth={2.4}/></span><span><strong>Acervo</strong><small>Ferramentas para YouTube</small></span></div><div className="nav-heading">UTILIDADES</div><nav aria-label="Ferramentas">{visibleItems.map(item => { const Icon = item.icon; return <button key={item.id} className={`nav-item ${activeTab === item.id ? 'active' : ''}`} onClick={() => setActiveTab(item.id)}><Icon size={19}/><span><strong>{item.label}</strong><small>{item.subtitle}</small></span></button>; })}</nav></div><div className="sidebar-bottom"><span className="status-dot"/> {localTools ? 'Ambiente local' : 'Versão web'} <small>{localTools ? 'Os dados do canal são acessados pela sua conexão.' : 'A migração permanece na versão local.'}</small></div></aside><main className="app-main"><header className="app-topbar"><span>Acervo / {items.find(x => x.id === activeTab)?.label}</span><span className="topbar-tag">YouTube Studio · utilidades</span></header><div className="app-content">{children}</div></main></div>;
}
