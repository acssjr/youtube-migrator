import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { Account, AppSettings } from '../types';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Trash2, Plus, CheckCircle2, AlertCircle } from 'lucide-react';

export function SettingsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [newAccountName, setNewAccountName] = useState('');
  const [settings, setSettings] = useState<AppSettings>({
    default_account_id: '',
    default_channel_id: '',
    temp_downloads_dir: 'downloads',
    theme: 'dark',
  });
  const [loading, setLoading] = useState(false);
  const [authStatus, setAuthStatus] = useState<{ type: 'success' | 'error' | null, msg: string }>({ type: null, msg: '' });

  useEffect(() => {
    loadSettings();
    loadAccounts();
    
    // Check URL params for authentication callback status
    const params = new URLSearchParams(window.location.search);
    if (params.get('auth') === 'success') {
      setAuthStatus({ type: 'success', msg: 'Conta do YouTube conectada com sucesso!' });
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (params.get('auth') === 'error') {
      const reason = params.get('reason') || 'Erro desconhecido.';
      setAuthStatus({ type: 'error', msg: `Falha ao autenticar: ${reason}` });
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  const loadSettings = async () => {
    try {
      const res = await api.settings.getSettings();
      if (res && res.settings) {
        setSettings(res.settings);
      }
    } catch (err) {
      console.error('Failed to load settings', err);
    }
  };

  const loadAccounts = async () => {
    try {
      const data = await api.auth.getAccounts();
      setAccounts(data);
    } catch (err) {
      console.error('Failed to load accounts', err);
    }
  };

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      await api.settings.updateSettings(settings);
      alert('Configurações salvas com sucesso!');
    } catch (err) {
      alert('Erro ao salvar configurações.');
    } finally {
      setLoading(false);
    }
  };

  const handleConnectAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = newAccountName.trim() || "Canal do YouTube";
    
    try {
      setLoading(true);
      const res = await api.auth.getAuthUrl(name);
      if (res.url) {
        // Redirect user to Google OAuth page
        window.location.href = res.url;
      }
    } catch (err) {
      alert('Erro ao requisitar autorização do Google: ' + err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAccount = async (id: number) => {
    if (!confirm('Deseja remover este canal?')) return;
    try {
      await api.auth.deleteAccount(id);
      loadAccounts();
    } catch (err) {
      alert('Erro ao remover conta.');
    }
  };

  return (
    <div className="space-y-6">
      {authStatus.type && (
        <div className={`p-4 rounded-lg flex items-center gap-3 border ${
          authStatus.type === 'success' 
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-500' 
            : 'bg-red-500/10 border-red-500/30 text-red-500'
        }`}>
          {authStatus.type === 'success' ? <CheckCircle2 className="h-5 w-5" /> : <AlertCircle className="h-5 w-5" />}
          <span className="text-sm font-medium">{authStatus.msg}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Connection OAuth Cards */}
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle>Contas do YouTube Conectadas</CardTitle>
            <CardDescription>
              Autentique e gerencie os tokens OAuth das contas do YouTube das quais você é administrador.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex-1 space-y-4">
            {accounts.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground text-sm border-2 border-dashed rounded-lg bg-muted/10">
                Nenhuma conta conectada. Conecte sua primeira conta abaixo.
              </div>
            ) : (
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {accounts.map((acc) => (
                  <div key={acc.id} className="flex items-center justify-between p-3 rounded-lg border bg-muted/20">
                    <div className="flex flex-col">
                      <span className="font-semibold text-sm">{acc.channel_title}</span>
                      <span className="text-xs text-muted-foreground">Perfil: {acc.account_name} ({acc.channel_id})</span>
                    </div>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      className="text-red-500 hover:text-red-700 hover:bg-red-500/10"
                      onClick={() => handleDeleteAccount(acc.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
            
            <form onSubmit={handleConnectAccount} className="pt-4 border-t space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Conectar Nova Conta</h4>
              <div className="flex gap-2">
                <Input
                  placeholder="Apelido da conta (ex: Filarmônica)"
                  value={newAccountName}
                  onChange={(e) => setNewAccountName(e.target.value)}
                  disabled={loading}
                />
                <Button type="submit" disabled={loading} className="gap-2 shrink-0">
                  <Plus className="h-4 w-4" />
                  Conectar
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {/* Configurations Card */}
        <Card>
          <CardHeader>
            <CardTitle>Configurações Globais</CardTitle>
            <CardDescription>
              Defina os padrões de migração, caminhos de download e tema visual.
            </CardDescription>
          </CardHeader>
          <form onSubmit={handleSaveSettings}>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Conta de Destino Padrão</label>
                <Select
                  value={settings.default_account_id}
                  onChange={(e) => setSettings({ ...settings, default_account_id: e.target.value })}
                >
                  <option value="">Selecione uma conta...</option>
                  {accounts.map(acc => (
                    <option key={acc.id} value={acc.channel_id}>{acc.channel_title} ({acc.account_name})</option>
                  ))}
                </Select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Pasta Temporária de Downloads</label>
                <Input
                  placeholder="downloads"
                  value={settings.temp_downloads_dir}
                  onChange={(e) => setSettings({ ...settings, temp_downloads_dir: e.target.value })}
                />
                <p className="text-[11px] text-muted-foreground">Caminho onde o yt-dlp salvará os arquivos temporariamente antes do upload.</p>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Tema do Sistema</label>
                <Select
                  value={settings.theme}
                  onChange={(e) => {
                    const theme = e.target.value as 'light' | 'dark';
                    setSettings({ ...settings, theme });
                    // Toggle html theme class
                    if (theme === 'dark') {
                      document.body.classList.add('dark');
                    } else {
                      document.body.classList.remove('dark');
                    }
                  }}
                >
                  <option value="dark">Escuro (Recomendado)</option>
                  <option value="light">Claro</option>
                </Select>
              </div>
            </CardContent>
            <CardFooter className="border-t pt-4 flex justify-end">
              <Button type="submit" disabled={loading}>
                Salvar Configurações
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  );
}
