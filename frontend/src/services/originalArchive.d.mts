export function safeRelativePath(value: string): string[];
export function hashBlob(blob: Blob, signal?: AbortSignal, progress?: (bytes: number) => void): Promise<string>;
export function manifestChunks<T>(files: T[], metadata: Record<string, unknown>, maxBytes?: number): Array<Record<string, unknown> & { files: T[] }>;
export function copyBlob(blob: Blob, handle: any, signal?: AbortSignal, progress?: (bytes: number) => void): Promise<void>;
