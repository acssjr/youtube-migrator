import { Account, Task, AppSettings, DiscoveryResponse, EmptyVideo, DescriptionProposal, ApplyResult, DownloadJob, DownloadStatus } from '../types';

const BASE_URL = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers || {}),
    },
  });

  if (!response.ok) {
    const errText = await response.text();
    let message = errText;
    try {
      const detail = JSON.parse(errText).detail;
      message = Array.isArray(detail) ? detail.map(item => (item.msg || 'Confira os dados enviados.').replace(/^Value error, /, '')).join(' ') : detail || errText;
    } catch { /* plain-text response */ }
    throw new Error(message || 'Não foi possível concluir a solicitação.');
  }

  return response.json();
}

export const api = {
  uploads: {
    ensembleVideos: (channelId: string, ensemble: string) => request<{ id: string; title: string }[]>(`/uploads/${encodeURIComponent(channelId)}/ensemble-videos?ensemble=${encodeURIComponent(ensemble)}`),
    playlists: (channelId: string) => request<{ id: string; title: string; privacy: 'private' | 'public' | 'unlisted' }[]>(`/uploads/${encodeURIComponent(channelId)}/playlists`),
    createPlaylist: (channelId: string, referenceId: string, title: string, videoIds: string[], privacy: 'private' | 'public' | 'unlisted') =>
      request<{ id: string; title: string; url: string; complete: boolean; items: { video_id: string; status: string; message?: string }[] }>('/uploads/playlists', { method: 'POST', body: JSON.stringify({ channel_id: channelId, reference_id: referenceId, title, video_ids: videoIds, privacy }) }),
    catalog: (channelId: string) => request<{ composers: string[]; arrangers: string[]; ensembles: string[] }>(`/uploads/${encodeURIComponent(channelId)}/catalog`),
    authorize: (channelId: string) => request<{ access_token: string }>('/uploads/authorize', { method: 'POST', body: JSON.stringify({ channel_id: channelId }) }),
    preview: (channelId: string, items: { id: string; title: string; identity: { work: string; composer: string; arranger: string } }[]) =>
      request<DescriptionProposal[]>('/uploads/preview', { method: 'POST', body: JSON.stringify({ channel_id: channelId, items }) }),
  },
  capabilities: () => request<{ local_tools: boolean; downloads: boolean }>('/capabilities'),
  downloads: {
    handoff: (sources: string[], format: 'mp3' | 'mp4', resolution: number, channelId?: string) =>
      request<{ url: string }>('/downloads/handoff', { method: 'POST', body: JSON.stringify({ sources, format, resolution, channel_id: channelId }) }),
    status: () => request<DownloadStatus>('/downloads/status'),
    channel: (channelId: string) => request<EmptyVideo[]>(`/downloads/channel/${encodeURIComponent(channelId)}`),
    jobs: () => request<DownloadJob[]>('/downloads/jobs'),
    create: (sources: string[], format: 'mp3' | 'mp4', resolution: number, channelId?: string) =>
      request<DownloadJob[]>('/downloads/jobs', { method: 'POST', body: JSON.stringify({ sources, format, resolution, channel_id: channelId }) }),
  },
  descriptions: {
    empty: (channelId: string) => request<EmptyVideo[]>(`/descriptions/${encodeURIComponent(channelId)}/empty`),
    preview: (channelId: string, videoIds: string[], overrides: Record<string, { work: string; composer: string; arranger: string }>) =>
      request<DescriptionProposal[]>('/descriptions/preview', { method: 'POST', body: JSON.stringify({ channel_id: channelId, video_ids: videoIds, overrides }) }),
    apply: (channelId: string, items: { video_id: string; description: string }[]) =>
      request<ApplyResult[]>('/descriptions/apply', { method: 'POST', body: JSON.stringify({ channel_id: channelId, items }) }),
  },
  auth: {
    getAuthUrl: (accountName: string) => 
      request<{ url: string }>(`/auth/url?account_name=${encodeURIComponent(accountName)}`),
    
    getAccounts: () => 
      request<Account[]>('/auth/accounts'),
    
    deleteAccount: (id: number) => 
      request<{ message: string }>(`/auth/accounts/${id}`, { method: 'DELETE' }),
  },
  
  channels: {
    discover: (sourceUrl: string) => 
      request<DiscoveryResponse>('/channels/discover', {
        method: 'POST',
        body: JSON.stringify({ source_url: sourceUrl }),
      }),
  },
  
  migrations: {
    queue: (payload: {
      tasks: any[];
      create_playlist?: boolean;
      playlist_name?: string;
      playlist_description?: string;
      playlist_privacy?: string;
    }) => 
      request<Task[]>('/migrations/queue', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    
    getTasks: () => 
      request<Task[]>('/migrations/tasks'),
    
    retry: (taskId: number) => 
      request<Task>(`/migrations/tasks/${taskId}/retry`, { method: 'POST' }),
  },
  
  settings: {
    getSettings: () => 
      request<{ settings: AppSettings }>('/settings'),
    
    updateSettings: (payload: Partial<AppSettings>) => 
      request<{ settings: AppSettings }>('/settings', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
  },
  
  logs: {
    getLogs: (file: 'downloads' | 'uploads' | 'errors', limit: number = 100) => 
      request<string[]>(`/logs?file=${file}&limit=${limit}`),
  }
};
