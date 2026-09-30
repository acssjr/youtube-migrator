import { AcervoRecord } from './acervoApi';
export interface DashboardVideo { id: string; title: string; description: string; composer: string; work: string; ensemble: string; catalog_ambiguous: boolean; events: { name: string; project: string; ensemble: string; performed_at: string }[] }
export interface PendingSummary { blank: DashboardVideo[]; credits: DashboardVideo[]; ambiguous: DashboardVideo[]; undated: AcervoRecord[]; outdated: DashboardVideo[]; originals: DashboardVideo[] | null; originalCount: number; approvedCount: number; latestBackup: AcervoRecord | null }
export function playlistIds(text: string): Set<string>;
export function buildArchivePending(videos: DashboardVideo[], records: AcervoRecord[], channelId: string): PendingSummary;
