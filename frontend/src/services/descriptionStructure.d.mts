export interface CommonStructure { mainName: string; mainInstagram: string; mainFollow: string; playlists: string }
export interface VideoStructure { ensemble: string; instagram: string; socialText: string; history: string; archive: string; includeArchive: boolean; guest: boolean; body: string }
export function baseStructure(): CommonStructure;
export function instagramUrl(value: string): string;
export function initialVideoStructure(structure?: {ensemble?: string; history?: string; social_text?: string; body?: string}): VideoStructure;
export function composeStructure(common: CommonStructure, video: VideoStructure): string;

export function followBlock(name: string, handle: string, exact: string): string;
