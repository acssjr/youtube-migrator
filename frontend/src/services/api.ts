import { Account, Task, AppSettings, DiscoveryResponse } from '../types';

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
    throw new Error(errText || 'Error processing request');
  }

  return response.json();
}

export const api = {
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
