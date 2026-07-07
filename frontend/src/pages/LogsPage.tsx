import { useState, useEffect, useRef } from 'react';
import { api } from '../services/api';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Terminal, RefreshCw, Download, Upload, AlertTriangle } from 'lucide-react';

export function LogsPage() {
  const [activeLog, setActiveLog] = useState<'downloads' | 'uploads' | 'errors'>('downloads');
  const [logLines, setLogLines] = useState<string[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const consoleEndRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    fetchLogs();
    
    // Poll logs every 2 seconds for live feeling
    const interval = setInterval(() => {
      fetchLogs();
    }, 2000);
    
    return () => clearInterval(interval);
  }, [activeLog]);

  useEffect(() => {
    if (autoScroll) {
      scrollToBottom();
    }
  }, [logLines, autoScroll]);

  const fetchLogs = async () => {
    try {
      const data = await api.logs.getLogs(activeLog);
      setLogLines(data);
    } catch (err) {
      console.error('Failed to fetch logs', err);
    }
  };

  const scrollToBottom = () => {
    consoleEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <Card className="flex flex-col h-[calc(100vh-12rem)] min-h-[500px]">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4 border-b shrink-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Terminal className="h-5 w-5 text-primary" />
            Logs de Execução
          </CardTitle>
          <CardDescription>
            Veja o console em tempo real do processamento de downloads, uploads e erros.
          </CardDescription>
        </div>
        
        {/* Log type filters */}
        <div className="flex gap-2">
          <Button
            variant={activeLog === 'downloads' ? 'default' : 'outline'}
            size="sm"
            className="gap-2"
            onClick={() => setActiveLog('downloads')}
          >
            <Download className="h-4 w-4" />
            Downloads
          </Button>
          <Button
            variant={activeLog === 'uploads' ? 'default' : 'outline'}
            size="sm"
            className="gap-2"
            onClick={() => setActiveLog('uploads')}
          >
            <Upload className="h-4 w-4" />
            Uploads
          </Button>
          <Button
            variant={activeLog === 'errors' ? 'default' : 'outline'}
            size="sm"
            className="gap-2 text-red-500 hover:text-red-500 hover:bg-red-500/10"
            onClick={() => setActiveLog('errors')}
          >
            <AlertTriangle className="h-4 w-4" />
            Erros
          </Button>
        </div>
      </CardHeader>
      
      {/* Console output */}
      <CardContent className="flex-1 overflow-y-auto bg-black text-slate-300 font-mono text-xs p-6 space-y-1 select-text">
        {logLines.length === 0 ? (
          <div className="text-zinc-600 italic">Nenhuma linha de log registrada nesta sessão.</div>
        ) : (
          logLines.map((line, index) => {
            let color = 'text-slate-300';
            if (line.includes('ERROR') || line.includes('Failed')) color = 'text-red-400';
            else if (line.includes('complete') || line.includes('Success') || line.includes('completed')) color = 'text-emerald-400';
            else if (line.includes('Downloading') || line.includes('Uploading')) color = 'text-sky-400';

            return (
              <div key={index} className={color}>
                {line}
              </div>
            );
          })
        )}
        <div ref={consoleEndRef} />
      </CardContent>
      
      {/* Footer controls */}
      <div className="p-4 border-t bg-muted/20 flex justify-between items-center shrink-0">
        <label className="flex items-center gap-2 text-xs font-semibold text-muted-foreground select-none cursor-pointer">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="rounded border-input text-primary focus:ring-primary h-4.5 w-4.5"
          />
          Rolar automaticamente para baixo
        </label>
        
        <Button variant="ghost" size="sm" onClick={fetchLogs} className="gap-2">
          <RefreshCw className="h-3.5 w-3.5" />
          Forçar Atualização
        </Button>
      </div>
    </Card>
  );
}
