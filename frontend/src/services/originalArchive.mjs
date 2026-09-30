import { createSHA256 } from 'hash-wasm';

export function safeRelativePath(value) {
  const parts = value.replaceAll('\\', '/').split('/');
  if (!parts.length || parts.some(part => !part || part === '.' || part === '..' || /[:\u0000-\u001f]/.test(part))) throw new Error('Caminho relativo inválido.');
  return parts;
}
export async function hashBlob(blob, signal, progress = () => {}) {
  const hash = await createSHA256();
  hash.init();
  const chunkSize = 4 * 1024 * 1024;
  for (let offset = 0; offset < blob.size; offset += chunkSize) {
    signal?.throwIfAborted();
    hash.update(new Uint8Array(await blob.slice(offset, offset + chunkSize).arrayBuffer()));
    progress(Math.min(blob.size, offset + chunkSize));
  }
  signal?.throwIfAborted();
  return hash.digest('hex');
}
export function manifestChunks(files, metadata, maxBytes = 180000) {
  const chunks = [];
  let current = [];
  for (const file of files) {
    if (new TextEncoder().encode(JSON.stringify({ ...metadata, files: [file] })).length > maxBytes) throw new Error('Um registro de arquivo excede o tamanho permitido.');
    if (new TextEncoder().encode(JSON.stringify({ ...metadata, files: [...current, file] })).length > maxBytes) {
      if (!current.length) throw new Error('Um registro de arquivo excede o tamanho permitido.');
      chunks.push({ ...metadata, files: current }); current = [];
    }
    current.push(file);
  }
  if (current.length) chunks.push({ ...metadata, files: current });
  return chunks;
}
export async function copyBlob(blob, handle, signal, progress = () => {}) {
  const writer = await handle.createWritable();
  try {
    for (let offset = 0; offset < blob.size; offset += 4 * 1024 * 1024) {
      signal?.throwIfAborted();
      const end = Math.min(blob.size, offset + 4 * 1024 * 1024);
      await writer.write(blob.slice(offset, end)); progress(end);
    }
    signal?.throwIfAborted(); await writer.close();
  } catch (error) { await writer.abort(); throw error; }
}
