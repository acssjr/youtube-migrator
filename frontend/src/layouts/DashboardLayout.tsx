import React from 'react';
import { Youtube, Settings, Terminal, ArrowRightLeft } from 'lucide-react';

interface DashboardLayoutProps {
  children: React.ReactNode;
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export function DashboardLayout({ children, activeTab, setActiveTab }: DashboardLayoutProps) {
  const menuItems = [
    { id: 'migration', label: 'Migração', icon: ArrowRightLeft },
    { id: 'settings', label: 'Configurações', icon: Settings },
    { id: 'logs', label: 'Console de Logs', icon: Terminal },
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      {/* Sidebar */}
      <aside className="w-64 border-r bg-card flex flex-col justify-between shrink-0">
        <div className="flex flex-col">
          {/* Brand header */}
          <div className="h-16 flex items-center px-6 border-b gap-3">
            <div className="p-1.5 rounded-lg bg-red-600 text-white flex items-center justify-center">
              <Youtube className="h-6 w-6" />
            </div>
            <div>
              <h1 className="font-bold tracking-tight text-sm">YT MIGRATOR</h1>
              <p className="text-[10px] text-muted-foreground uppercase tracking-widest font-semibold">Local Sync Tool</p>
            </div>
          </div>
          
          {/* Navigation Links */}
          <nav className="p-4 space-y-1">
            {menuItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center px-4 py-2.5 rounded-lg text-sm font-medium transition-all gap-3 ${
                    isActive
                      ? 'bg-primary text-primary-foreground shadow-md font-semibold'
                      : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
                  }`}
                >
                  <Icon className="h-4.5 w-4.5" />
                  {item.label}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Sidebar Footer info */}
        <div className="p-4 border-t text-[11px] text-muted-foreground bg-muted/20">
          <div className="flex items-center justify-between">
            <span>Status do Servidor:</span>
            <span className="flex items-center gap-1.5 font-medium text-emerald-500">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
              Conectado
            </span>
          </div>
          <div className="mt-1 text-[10px] text-center font-mono">v0.1.0 (Localhost)</div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden bg-background">
        {/* Header bar */}
        <header className="h-16 border-b flex items-center justify-between px-8 bg-card shrink-0">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-semibold tracking-tight">
              {menuItems.find(i => i.id === activeTab)?.label}
            </h2>
          </div>
          
          {/* Profile indicator */}
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground font-medium">Migrador de Canais</span>
            <div className="h-8 w-8 rounded-full bg-primary/20 flex items-center justify-center font-bold text-primary text-xs border border-primary/30">
              YT
            </div>
          </div>
        </header>

        {/* Scrollable Main Area */}
        <div className="flex-1 overflow-auto p-8">
          <div className="max-w-7xl mx-auto h-full">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
