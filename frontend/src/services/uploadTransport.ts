export interface UploadReply { status: number; text: string; header: (name: string) => string | null }
export type UploadRequest = (method: string, url: string, headers: Record<string, string>, body: Blob | string | null, signal: AbortSignal, progress?: (bytes: number) => void) => Promise<UploadReply>;

export const uploadRequest: UploadRequest = (method, url, headers, body, signal, progress) => new Promise((resolve, reject) => {
  const xhr = new XMLHttpRequest();
  const abort = () => xhr.abort();
  if (signal.aborted) { reject(new DOMException('Pausado', 'AbortError')); return; }
  xhr.open(method, url);
  xhr.timeout = 120000;
  Object.entries(headers).forEach(([name, value]) => xhr.setRequestHeader(name, value));
  const cleanup = () => signal.removeEventListener('abort', abort);
  signal.addEventListener('abort', abort, { once: true });
  if (progress) xhr.upload.onprogress = event => progress(event.loaded);
  xhr.onload = () => { cleanup(); resolve({ status: xhr.status, text: xhr.responseText, header: name => xhr.getResponseHeader(name) }); };
  xhr.onerror = xhr.ontimeout = () => { cleanup(); resolve({ status: 0, text: '', header: () => null }); };
  xhr.onabort = () => { cleanup(); reject(new DOMException('Pausado', 'AbortError')); };
  xhr.send(body);
});

export function validateSessionUrl(value: string): string {
  const url = new URL(value);
  if (url.protocol !== 'https:' || url.hostname !== 'www.googleapis.com' || url.pathname !== '/upload/youtube/v3/videos' || !url.searchParams.get('upload_id')) {
    throw new Error('A sessão de upload recebida é inválida.');
  }
  return url.href;
}

function received(reply: UploadReply, total: number): number {
  const range = reply.header('Range');
  if (!range) return 0;
  const match = /^bytes=0-(\d+)$/.exec(range);
  const offset = match ? Number(match[1]) + 1 : -1;
  if (offset < 0 || offset > total) throw new Error('O YouTube retornou um progresso inválido.');
  return offset;
}

function apiError(reply: UploadReply): Error {
  if (reply.status === 404 || reply.status === 410) return new Error('A sessão expirou. Confira o canal antes de reiniciar este arquivo para evitar um envio duplicado.');
  try { return new Error(JSON.parse(reply.text).error.message || `Erro do YouTube (${reply.status}).`); }
  catch { return new Error(reply.status ? `Erro do YouTube (${reply.status}).` : 'A conexão falhou. Retome o envio quando a internet voltar.'); }
}

const wait = (ms: number, signal: AbortSignal) => new Promise<void>((resolve, reject) => {
  const abort = () => { clearTimeout(timer); reject(new DOMException('Pausado', 'AbortError')); };
  const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, ms);
  if (signal.aborted) { abort(); return; }
  signal.addEventListener('abort', abort, { once: true });
});

export interface UploadOptions {
  file: File;
  metadata: { snippet: { title: string; description: string; categoryId: string }; status: { privacyStatus: string; selfDeclaredMadeForKids: boolean } };
  sessionUrl?: string;
  signal: AbortSignal;
  getToken: () => Promise<string>;
  onSession: (url: string) => void;
  onCheckpoint: (bytes: number) => void;
  onProgress: (bytes: number) => void;
  request?: UploadRequest;
  delay?: (ms: number, signal: AbortSignal) => Promise<void>;
}

export async function sendUpload(options: UploadOptions): Promise<{ id: string; privacy: string }> {
  const { file, signal } = options;
  const request = options.request || uploadRequest;
  const delay = options.delay || wait;
  const mime = file.type.startsWith('video/') ? file.type : 'application/octet-stream';
  let token = await options.getToken();
  let url = options.sessionUrl;
  if (signal.aborted) throw new DOMException('Pausado', 'AbortError');
  if (!url) {
    const reply = await request('POST', 'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status', {
      Authorization: `Bearer ${token}`, 'Content-Type': 'application/json',
      'X-Upload-Content-Length': String(file.size), 'X-Upload-Content-Type': mime,
    }, JSON.stringify(options.metadata), signal);
    if (reply.status < 200 || reply.status >= 300) throw apiError(reply);
    url = validateSessionUrl(reply.header('Location') || '');
    options.onSession(url);
  } else url = validateSessionUrl(url);

  let offset = 0;
  let probe = !!options.sessionUrl;
  let failures = 0;
  const chunk = 8 * 1024 * 1024; // Nonfinal chunks must be multiples of 256 KiB.
  while (true) {
    if (signal.aborted) throw new DOMException('Pausado', 'AbortError');
    const end = Math.min(offset + chunk, file.size);
    const reply = await request('PUT', url, {
      Authorization: `Bearer ${token}`, 'Content-Type': mime,
      'Content-Range': probe ? `bytes */${file.size}` : `bytes ${offset}-${end - 1}/${file.size}`,
    }, probe ? null : file.slice(offset, end), signal, bytes => options.onProgress(Math.min(offset + bytes, file.size)));
    if (reply.status === 200 || reply.status === 201) {
      const video = JSON.parse(reply.text);
      if (!video.id) throw new Error('O YouTube não confirmou o identificador do vídeo. Retome para conferir a sessão.');
      options.onCheckpoint(file.size);
      return { id: video.id, privacy: video.status?.privacyStatus || '' };
    }
    if (reply.status === 308) {
      const next = received(reply, file.size);
      if (!probe && next <= offset) throw new Error('O YouTube não confirmou o bloco enviado. Retome para conferir o progresso.');
      if (next === file.size) {
        if (++failures > 5) throw new Error('O YouTube recebeu os dados, mas ainda não confirmou o vídeo. Retome para conferir a sessão.');
        await delay(1000 * 2 ** (failures - 1), signal);
      } else failures = 0;
      offset = next;
      options.onCheckpoint(offset);
      probe = offset === file.size;
      continue;
    }
    if (reply.status === 0 || reply.status === 401 || reply.status === 429 || [500, 502, 503, 504].includes(reply.status)) {
      if (++failures > 5) throw apiError(reply);
      if (reply.status === 401) token = await options.getToken();
      const retryAfter = Number(reply.header('Retry-After'));
      await delay(Math.min(60000, Math.max(1000 * 2 ** (failures - 1), Number.isFinite(retryAfter) ? retryAfter * 1000 : 0)), signal);
      probe = true; // Never guess the byte offset after a failed transfer.
      continue;
    }
    throw apiError(reply);
  }
}
