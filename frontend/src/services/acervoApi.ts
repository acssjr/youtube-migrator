export interface AcervoRecord<T = Record<string, any>> { id: string; kind: string; payload: T; created_at: string; updated_at: string }
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/acervo${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options?.headers } });
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Não foi possível salvar os dados.');
  return result;
}
export const acervoApi = {
  records: <T = Record<string, any>>(kind?: string) => request<AcervoRecord<T>[]>(`/records${kind ? `?kind=${encodeURIComponent(kind)}` : ''}`),
  create: <T = Record<string, any>>(kind: string, payload: T) => request<AcervoRecord<T>>('/records', { method: 'POST', body: JSON.stringify({ kind, payload }) }),
  update: <T = Record<string, any>>(id: string, payload: T, expected_updated_at?: string) => request<AcervoRecord<T>>(`/records/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ payload, expected_updated_at }) }),
  remove: (id: string) => request<{ deleted: boolean }>(`/records/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  versions: (id: string) => request<AcervoRecord[]>(`/records/${encodeURIComponent(id)}/versions`),
};
