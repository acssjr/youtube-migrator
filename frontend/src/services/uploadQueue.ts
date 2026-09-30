import { api } from './api';
import { DescriptionProposal } from '../types';
import { sendUpload } from './uploadTransport';
export { composeUploadTitle } from './uploadMetadata';

export type Privacy = 'private' | 'unlisted' | 'public';
export interface UploadItem {
  id: string; name: string; size: number; modified: number; title: string; description: string;
  identity: { work: string; composer: string; arranger: string };
  genre: string; ensemble: string; titlePreferences?: {separator:string;includeGenre:boolean;includeComposer:boolean;includeArranger:boolean;includeEnsemble:boolean};
  privacy: Privacy; madeForKids: boolean; included: boolean;
  status: 'draft' | 'uploading' | 'paused' | 'error' | 'completed';
  bytes: number; sessionUrl?: string; videoId?: string; actualPrivacy?: string; error?: string;
  proposal?: DescriptionProposal;
}
const storageKey = 'acervo-upload-queue-v1';
const files = new Map<string, File>();
const listeners = new Set<() => void>();
function restore(): { channelId: string; items: UploadItem[] } {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || 'null');
    if (saved && Array.isArray(saved.items)) return { channelId: saved.channelId || '', items: saved.items.map((item: UploadItem) => ({ ...item, status: item.status === 'uploading' ? 'paused' : item.status })) };
  } catch { /* A malformed draft must not block the rest of the app. */ }
  return { channelId: '', items: [] };
}
let state = { ...restore(), running: false, storageError: '' };
let controller: AbortController | undefined;
function emit(persist = true) {
  if (persist) {
    try { localStorage.setItem(storageKey, JSON.stringify({ channelId: state.channelId, items: state.items })); }
    catch { state = { ...state, storageError: 'O navegador não conseguiu salvar a fila. Mantenha esta aba aberta.' }; }
  }
  listeners.forEach(listener => listener());
}
export const uploadQueue = {
  subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
  snapshot: () => state,
  hasFile: (id: string) => files.has(id),
  setChannel: (channelId: string) => { if (!state.running && !state.items.length) { state = { ...state, channelId }; emit(); } },
  patch: (id: string, patch: Partial<UploadItem>, persist = true) => {
    state = { ...state, items: state.items.map(item => item.id === id ? { ...item, ...patch } : item) }; emit(persist);
  },
  add: (selection: File[], privacy: Privacy, channelId: string, ensemble = '', titlePreferences?: UploadItem['titlePreferences']) => {
    if (state.running) return;
    const items = [...state.items];
    for (const file of selection) {
      if (!file.size || (!file.type.startsWith('video/') && !/\.(mp4|mov|mkv|webm|avi|m4v|mpeg|mpg|mts|m2ts|wmv)$/i.test(file.name))) continue;
      const known = items.find(item => item.name === file.name && item.size === file.size && item.modified === file.lastModified);
      if (known) { files.set(known.id, file); continue; }
      if (items.length >= 50) break;
      const id = crypto.randomUUID(); files.set(id, file);
      items.push({ id, name: file.name, size: file.size, modified: file.lastModified,
        title: '', description: '', genre: '', ensemble, titlePreferences,
        identity: { work: '', composer: '', arranger: '' }, privacy, madeForKids: false, included: true, status: 'draft', bytes: 0 });
    }
    state = { ...state, channelId: state.channelId || channelId, items }; emit();
  },
  remove: (id: string) => { if (state.running) return; files.delete(id); state = { ...state, items: state.items.filter(item => item.id !== id) }; emit(); },
  clear: () => { if (state.running) return; files.clear(); state = { ...state, items: [] }; emit(); },
  pause: () => controller?.abort(),
  start: async () => {
    if (navigator.locks) {
      return navigator.locks.request('acervo-upload-queue', { ifAvailable: true }, async lock => {
        if (!lock) throw new Error('Há um envio ativo em outra aba. Pause essa fila antes de iniciar aqui.');
        await runQueue();
      });
    }
    await runQueue();
  },
};
async function runQueue() {
    if (state.running) return;
    const pending = state.items.filter(item => item.included && item.status !== 'completed');
    if (!state.channelId || !pending.length) throw new Error('Selecione um canal e arquivos para enviar.');
    if (pending.some(item => !files.has(item.id))) throw new Error('Selecione novamente os arquivos pendentes para retomar esta fila.');
    if (pending.some(item => !item.identity.work.trim() || !item.title.trim() || /[<>]/.test(item.title) || item.title.length > 100 || item.description.length > 5000 || /[<>]/.test(item.description))) throw new Error('Preencha o nome de cada obra e confira os títulos e descrições. O YouTube não aceita < ou > nesses campos.');
    controller = new AbortController();
    state = { ...state, running: true }; emit();
    try {
      for (const item of pending) {
        if (controller.signal.aborted) break;
        uploadQueue.patch(item.id, { status: 'uploading', error: '' });
        try {
          const result = await sendUpload({ file: files.get(item.id)!, sessionUrl: item.sessionUrl, signal: controller.signal,
            metadata: { snippet: { title: item.title.trim(), description: item.description, categoryId: '10' }, status: { privacyStatus: item.privacy, selfDeclaredMadeForKids: item.madeForKids } },
            getToken: async () => (await api.uploads.authorize(state.channelId)).access_token,
            onSession: sessionUrl => uploadQueue.patch(item.id, { sessionUrl }),
            onCheckpoint: bytes => uploadQueue.patch(item.id, { bytes }),
            onProgress: bytes => uploadQueue.patch(item.id, { bytes }, false),
          });
          uploadQueue.patch(item.id, { status: 'completed', videoId: result.id, actualPrivacy: result.privacy, sessionUrl: undefined, bytes: item.size });
          files.delete(item.id);
        } catch (error) {
          const paused = controller.signal.aborted;
          uploadQueue.patch(item.id, { status: paused ? 'paused' : 'error', error: paused ? '' : String(error).replace(/^Error: /, '') });
          break; // Let the user resolve authorization/quota failures before the next video.
        }
      }
    } finally { controller = undefined; state = { ...state, running: false }; emit(); }
}
window.addEventListener('beforeunload', event => { if (state.running) { event.preventDefault(); event.returnValue = ''; } });
