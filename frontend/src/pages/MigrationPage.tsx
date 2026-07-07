import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { Account, VideoInfo, Task, PlaylistInfo } from '../types';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Progress } from '@/components/ui/Progress';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { 
  Search, Link, Play, AlertCircle, CheckCircle, 
  HelpCircle, RefreshCw, Clock, ArrowRight 
} from 'lucide-react';

export function MigrationPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [sourceUrl, setSourceUrl] = useState('');
  const [discoveredVideos, setDiscoveredVideos] = useState<VideoInfo[]>([]);
  const [selectedVideoIds, setSelectedVideoIds] = useState<string[]>([]);
  
  // Search & Filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<'title' | 'published_at' | 'view_count'>('published_at');
  
  // Selection override & Upload configuration
  const [targetAccountId, setTargetAccountId] = useState('');
  const [privacyStatus, setPrivacyStatus] = useState<'public' | 'unlisted' | 'private'>('private');
  
  // Metadata overrides for the currently selected video (sidebar detail)
  const [activeVideoId, setActiveVideoId] = useState<string | null>(null);
  const [metadataOverrides, setMetadataOverrides] = useState<Record<string, Partial<VideoInfo>>>({});

  // Playlist configuration overrides
  const [discoveredPlaylist, setDiscoveredPlaylist] = useState<PlaylistInfo | null>(null);
  const [createPlaylist, setCreatePlaylist] = useState(false);
  const [playlistName, setPlaylistName] = useState('');
  const [playlistDescription, setPlaylistDescription] = useState('');

  // Active queue tasks
  const [queueTasks, setQueueTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadAccounts();
    loadQueue();

    // Poll queue status every 3 seconds to update progress bars
    const interval = setInterval(() => {
      loadQueue();
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  const loadAccounts = async () => {
    try {
      const data = await api.auth.getAccounts();
      setAccounts(data);
      if (data.length > 0) {
        setTargetAccountId(data[0].channel_id);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const loadQueue = async () => {
    try {
      const tasks = await api.migrations.getTasks();
      setQueueTasks(tasks);
    } catch (err) {
      console.error(err);
    }
  };

  const handleDiscover = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceUrl.trim()) return;

    try {
      setLoading(true);
      const data = await api.channels.discover(sourceUrl);
      setDiscoveredVideos(data.videos);
      setDiscoveredPlaylist(data.playlist || null);
      setSelectedVideoIds([]);
      setActiveVideoId(data.videos[0]?.id || null);
      
      // Auto-configure playlist options if playlist was found
      if (data.playlist) {
        setCreatePlaylist(true);
        setPlaylistName(data.playlist.title);
        setPlaylistDescription(data.playlist.description || '');
      } else {
        setCreatePlaylist(false);
        setPlaylistName('');
        setPlaylistDescription('');
      }
    } catch (err) {
      alert('Falha ao descobrir vídeos: ' + err);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleSelectAll = () => {
    if (selectedVideoIds.length === filteredVideos.length) {
      setSelectedVideoIds([]);
    } else {
      setSelectedVideoIds(filteredVideos.map(v => v.id));
    }
  };

  const handleToggleSelectVideo = (id: string) => {
    if (selectedVideoIds.includes(id)) {
      setSelectedVideoIds(selectedVideoIds.filter(vId => vId !== id));
    } else {
      setSelectedVideoIds([...selectedVideoIds, id]);
    }
  };

  const handleMetadataChange = (videoId: string, field: keyof VideoInfo, value: any) => {
    setMetadataOverrides(prev => ({
      ...prev,
      [videoId]: {
        ...prev[videoId],
        [field]: value
      }
    }));
  };

  const handleStartMigration = async () => {
    if (selectedVideoIds.length === 0) {
      alert('Por favor, selecione pelo menos um vídeo para migrar.');
      return;
    }
    if (!targetAccountId) {
      alert('Selecione uma conta de destino.');
      return;
    }

    const confirmMigration = confirm(`Deseja iniciar a migração de ${selectedVideoIds.length} vídeo(s) para o canal de destino?`);
    if (!confirmMigration) return;

    const sourceChannelTitle = discoveredPlaylist?.title || "Canal de Origem";
    
    // Prepare payload tasks
    const tasksPayload = selectedVideoIds.map(vId => {
      const video = discoveredVideos.find(v => v.id === vId)!;
      const overrides = metadataOverrides[vId] || {};
      
      return {
        video_id: video.id,
        title: overrides.title || video.title,
        description: overrides.description || video.description || "",
        tags: overrides.tags || video.tags || [],
        category_id: overrides.category_id || video.category_id || "22",
        language: overrides.default_language || video.default_language || "pt",
        thumbnail_url: video.thumbnail_url,
        
        source_channel_id: "source_channel",
        source_channel_title: sourceChannelTitle,
        target_channel_id: targetAccountId,
        privacy_status: privacyStatus,
        scheduled_at: null
      };
    });

    const payload = {
      tasks: tasksPayload,
      create_playlist: createPlaylist,
      playlist_name: createPlaylist ? playlistName : undefined,
      playlist_description: createPlaylist ? playlistDescription : undefined,
      playlist_privacy: createPlaylist ? privacyStatus : undefined,
      playlist_thumbnail_url: (createPlaylist && discoveredPlaylist) ? discoveredPlaylist.thumbnail_url : undefined
    };

    try {
      setLoading(true);
      await api.migrations.queue(payload);
      setSelectedVideoIds([]);
      loadQueue();
      alert('Migrações adicionadas à fila com sucesso!');
    } catch (err) {
      alert('Erro ao agendar migrações: ' + err);
    } finally {
      setLoading(false);
    }
  };

  const handleRetryTask = async (taskId: number) => {
    try {
      await api.migrations.retry(taskId);
      loadQueue();
    } catch (err) {
      alert('Erro ao reiniciar tarefa.');
    }
  };

  // Filter and sort discovered videos
  const filteredVideos = discoveredVideos
    .filter(v => v.title.toLowerCase().includes(searchQuery.toLowerCase()))
    .sort((a, b) => {
      if (sortField === 'title') return a.title.localeCompare(b.title);
      if (sortField === 'view_count') return (b.view_count || 0) - (a.view_count || 0);
      return (b.published_at || '').localeCompare(a.published_at || '');
    });

  const activeVideo = discoveredVideos.find(v => v.id === activeVideoId);
  const activeOverrides = activeVideoId ? metadataOverrides[activeVideoId] || {} : {};

  // Task count summaries
  const runningTasks = queueTasks.filter(t => t.status === 'downloading' || t.status === 'uploading');
  const completedTasks = queueTasks.filter(t => t.status === 'completed');
  const errorTasks = queueTasks.filter(t => t.status === 'error');

  return (
    <div className="space-y-6">
      {/* 1. Discovery input bar */}
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleDiscover} className="flex gap-3">
            <div className="relative flex-1">
              <Link className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Insira URL do canal, playlist, link do vídeo ou ID..."
                className="pl-9"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                disabled={loading}
              />
            </div>
            <Button type="submit" disabled={loading || !sourceUrl.trim()} className="gap-2 shrink-0">
              {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              Descobrir Vídeos
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* 2. Playlist Info Card if discovered */}
      {discoveredPlaylist && (
        <Card className="bg-primary/5 border-primary/20 overflow-hidden">
          <CardContent className="p-4 flex gap-4 items-center">
            {discoveredPlaylist.thumbnail_url && (
              <img
                src={discoveredPlaylist.thumbnail_url}
                alt="Playlist cover"
                className="w-24 h-24 object-cover rounded border bg-black shadow-md shrink-0 animate-in fade-in zoom-in-95 duration-200"
              />
            )}
            <div className="flex-1 space-y-1">
              <span className="text-[10px] font-bold text-primary uppercase tracking-wider">Playlist Encontrada</span>
              <h3 className="text-lg font-bold text-foreground">{discoveredPlaylist.title}</h3>
              <p className="text-xs text-muted-foreground line-clamp-2 max-w-2xl">{discoveredPlaylist.description || 'Sem descrição'}</p>
              <div className="text-xs text-muted-foreground flex gap-3 font-semibold mt-1">
                <span>{discoveredPlaylist.video_count} vídeos encontrados</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main interactive split columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Videos Table Column */}
        <div className="lg:col-span-2 space-y-4">
          <Card className="h-[500px] flex flex-col">
            <CardHeader className="flex flex-row items-center justify-between pb-3 border-b shrink-0">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  <Play className="h-4 w-4 text-primary fill-primary" />
                  Vídeos Encontrados ({filteredVideos.length})
                </CardTitle>
              </div>
              
              <div className="flex gap-2 items-center">
                <Input
                  placeholder="Pesquisar..."
                  className="w-40 h-8"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                <Select
                  className="w-32 h-8 py-0"
                  value={sortField}
                  onChange={(e) => setSortField(e.target.value as any)}
                >
                  <option value="published_at">Publicação</option>
                  <option value="title">Título</option>
                  <option value="view_count">Visualizações</option>
                </Select>
              </div>
            </CardHeader>
            
            <CardContent className="flex-1 overflow-auto p-0">
              {discoveredVideos.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-muted-foreground text-sm">
                  <HelpCircle className="h-8 w-8 mb-2 opacity-50" />
                  Nenhum vídeo descoberto. Insira um link acima.
                </div>
              ) : (
                <Table>
                  <TableHeader className="bg-muted/10 sticky top-0 bg-background z-10">
                    <TableRow>
                      <TableHead className="w-12 text-center">
                        <input
                          type="checkbox"
                          checked={selectedVideoIds.length === filteredVideos.length && filteredVideos.length > 0}
                          onChange={handleToggleSelectAll}
                          className="rounded border-input text-primary focus:ring-ring"
                        />
                      </TableHead>
                      <TableHead className="w-20">Thumbnail</TableHead>
                      <TableHead>Título</TableHead>
                      <TableHead className="w-24">Duração</TableHead>
                      <TableHead className="w-28">Publicação</TableHead>
                      <TableHead className="w-28 text-right">Views</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredVideos.map((video) => {
                      const isSelected = selectedVideoIds.includes(video.id);
                      const isActive = activeVideoId === video.id;
                      return (
                        <TableRow
                          key={video.id}
                          className={`cursor-pointer ${isActive ? 'bg-muted/30 border-l-2 border-l-primary' : ''}`}
                          onClick={() => setActiveVideoId(video.id)}
                        >
                          <TableCell className="text-center" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => handleToggleSelectVideo(video.id)}
                              className="rounded border-input text-primary focus:ring-ring cursor-pointer"
                            />
                          </TableCell>
                          <TableCell>
                            <img
                              src={video.thumbnail_url}
                              alt="thumb"
                              className="h-10 w-16 object-cover rounded border bg-black shadow-sm"
                            />
                          </TableCell>
                          <TableCell className="font-medium max-w-xs truncate text-xs">
                            {video.title}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground flex items-center gap-1 mt-3">
                            <Clock className="h-3 w-3" />
                            {video.duration || '--:--'}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {video.published_at || 'Desconhecida'}
                          </TableCell>
                          <TableCell className="text-xs text-right font-mono pr-4">
                            {video.view_count?.toLocaleString() || 0}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Metadata Configuration Column */}
        <div className="space-y-4">
          <Card className="h-[500px] flex flex-col">
            <CardHeader className="pb-3 border-b shrink-0">
              <CardTitle className="text-base">Configurar Metadados</CardTitle>
              <CardDescription>Edite as informações antes de migrar.</CardDescription>
            </CardHeader>
            
            <CardContent className="flex-1 overflow-auto py-4 space-y-4">
              {!activeVideo ? (
                <div className="h-full flex flex-col items-center justify-center text-muted-foreground text-sm text-center px-4">
                  Selecione um vídeo na tabela para editar seus metadados individuais.
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="aspect-video w-full rounded border bg-black overflow-hidden shadow-md relative">
                    <img src={activeVideo.thumbnail_url} alt="thumbnail" className="object-cover w-full h-full" />
                    <span className="absolute bottom-2 right-2 text-[10px] font-bold font-mono px-1 py-0.5 rounded bg-black/85 text-white">
                      {activeVideo.duration}
                    </span>
                  </div>

                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-muted-foreground uppercase">Título do Vídeo</label>
                    <Input
                      value={activeOverrides.title ?? activeVideo.title}
                      onChange={(e) => handleMetadataChange(activeVideo.id, 'title', e.target.value)}
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-muted-foreground uppercase">Descrição</label>
                    <textarea
                      className="w-full text-xs p-2 rounded border border-input bg-transparent placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring min-h-20"
                      value={activeOverrides.description ?? activeVideo.description}
                      onChange={(e) => handleMetadataChange(activeVideo.id, 'description', e.target.value)}
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-muted-foreground uppercase">Tags (separadas por vírgula)</label>
                    <Input
                      placeholder="tag1, tag2, tag3"
                      value={activeOverrides.tags ? activeOverrides.tags.join(', ') : (activeVideo.tags ? activeVideo.tags.join(', ') : '')}
                      onChange={(e) => handleMetadataChange(activeVideo.id, 'tags', e.target.value.split(',').map(t => t.trim()))}
                    />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Migration Actions and Setup */}
      {selectedVideoIds.length > 0 && (
        <Card className="bg-muted/10 border-primary/20">
          <CardContent className="pt-6 space-y-4">
            <div className="flex flex-wrap gap-6 items-end justify-between border-b pb-4">
              <div className="flex gap-4 items-center flex-wrap">
                <div className="space-y-1">
                  <span className="text-[10px] font-bold text-muted-foreground uppercase">Conta de Destino</span>
                  <Select
                    value={targetAccountId}
                    onChange={(e) => setTargetAccountId(e.target.value)}
                    className="w-56"
                  >
                    <option value="">Selecione...</option>
                    {accounts.map(acc => (
                      <option key={acc.id} value={acc.channel_id}>{acc.channel_title} ({acc.account_name})</option>
                    ))}
                  </Select>
                </div>

                <div className="space-y-1">
                  <span className="text-[10px] font-bold text-muted-foreground uppercase">Privacidade dos Vídeos</span>
                  <Select
                    value={privacyStatus}
                    onChange={(e) => setPrivacyStatus(e.target.value as any)}
                    className="w-36"
                  >
                    <option value="private">Privado</option>
                    <option value="unlisted">Não listado</option>
                    <option value="public">Público</option>
                  </Select>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <span className="text-xs text-muted-foreground font-semibold">
                  {selectedVideoIds.length} vídeo(s) selecionado(s)
                </span>
                <Button onClick={handleStartMigration} disabled={loading} className="gap-2 font-bold px-6">
                  Iniciar Migração
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Playlist migration options */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="createPlaylistCheckbox"
                  checked={createPlaylist}
                  onChange={(e) => setCreatePlaylist(e.target.checked)}
                  className="rounded border-input text-primary focus:ring-ring cursor-pointer h-4 w-4"
                />
                <label htmlFor="createPlaylistCheckbox" className="text-sm font-semibold cursor-pointer select-none">
                  Criar playlist correspondente no canal de destino
                </label>
              </div>

              {createPlaylist && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 border rounded bg-background/50 animate-in fade-in slide-in-from-top-2 duration-200">
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-muted-foreground uppercase">Nome da Playlist de Destino</label>
                    <Input
                      placeholder="Nome da Playlist"
                      value={playlistName}
                      onChange={(e) => setPlaylistName(e.target.value)}
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-muted-foreground uppercase">Descrição da Playlist</label>
                    <textarea
                      placeholder="Descrição da playlist de destino"
                      className="w-full text-xs p-2 rounded border border-input bg-transparent placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring min-h-[38px] h-[38px]"
                      value={playlistDescription}
                      onChange={(e) => setPlaylistDescription(e.target.value)}
                    />
                  </div>

                  {discoveredPlaylist?.thumbnail_url && (
                    <div className="md:col-span-2 flex items-center gap-2 text-xs text-muted-foreground mt-1">
                      <span className="font-semibold text-emerald-500">✓ Capa da Playlist detectada:</span>
                      <a href={discoveredPlaylist.thumbnail_url} target="_blank" rel="noreferrer" className="underline truncate max-w-md text-primary font-mono text-[10px]">
                        {discoveredPlaylist.thumbnail_url}
                      </a>
                      <span>(será migrada automaticamente)</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Queue Progress section */}
      <Card>
        <CardHeader className="pb-3 border-b flex flex-row justify-between items-center space-y-0">
          <div>
            <CardTitle className="text-base">Fila de Migrações</CardTitle>
            <CardDescription>Status das migrações em lote enviadas para processamento.</CardDescription>
          </div>
          
          <div className="flex gap-3 text-xs">
            <span className="flex items-center gap-1 text-sky-400 font-semibold">
              <Clock className="h-3.5 w-3.5" />
              {runningTasks.length} processando
            </span>
            <span className="flex items-center gap-1 text-emerald-400 font-semibold">
              <CheckCircle className="h-3.5 w-3.5" />
              {completedTasks.length} concluídos
            </span>
            <span className="flex items-center gap-1 text-red-400 font-semibold">
              <AlertCircle className="h-3.5 w-3.5" />
              {errorTasks.length} erros
            </span>
          </div>
        </CardHeader>
        
        <CardContent className="p-0 max-h-60 overflow-y-auto">
          {queueTasks.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-sm">
              Nenhuma tarefa de migração iniciada.
            </div>
          ) : (
            <Table>
              <TableHeader className="bg-muted/10 sticky top-0 bg-background z-10">
                <TableRow>
                  <TableHead className="w-16">ID</TableHead>
                  <TableHead>Título</TableHead>
                  <TableHead>Destino</TableHead>
                  <TableHead className="w-48">Status</TableHead>
                  <TableHead className="w-64">Progresso</TableHead>
                  <TableHead className="w-20 text-center">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {queueTasks.map((task) => (
                  <TableRow key={task.id}>
                    <TableCell className="font-mono text-xs">#{task.id}</TableCell>
                    <TableCell className="max-w-xs truncate text-xs font-semibold">{task.title}</TableCell>
                    <TableCell className="text-xs">{task.target_channel_title || task.target_channel_id}</TableCell>
                    <TableCell>
                      {task.status === 'pending' && <span className="px-2 py-0.5 rounded bg-zinc-500/10 border border-zinc-500/30 text-zinc-400 text-[10px] font-bold uppercase">Aguardando</span>}
                      {task.status === 'downloading' && <span className="px-2 py-0.5 rounded bg-sky-500/10 border border-sky-500/30 text-sky-400 text-[10px] font-bold uppercase animate-pulse">Baixando</span>}
                      {task.status === 'uploading' && <span className="px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 text-[10px] font-bold uppercase animate-pulse">Enviando</span>}
                      {task.status === 'completed' && <span className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold uppercase">Concluído</span>}
                      {task.status === 'error' && (
                        <div className="flex flex-col gap-0.5">
                          <span className="w-fit px-2 py-0.5 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-[10px] font-bold uppercase">Erro</span>
                          <span className="text-[10px] text-red-400 truncate max-w-xs">{task.error_message}</span>
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <Progress value={task.progress} />
                        <span className="text-[10px] text-muted-foreground font-mono font-semibold">{task.progress.toFixed(0)}%</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      {task.status === 'error' && (
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="h-7 text-xs gap-1 hover:bg-muted"
                          onClick={() => handleRetryTask(task.id)}
                        >
                          <RefreshCw className="h-3 w-3" />
                          Reprocessar
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
