export function composeUploadTitle(item: { genre: string; ensemble: string; identity: { work: string; composer: string; arranger: string }; titlePreferences?: {separator:string;includeGenre:boolean;includeComposer:boolean;includeArranger:boolean;includeEnsemble:boolean} }): string {
  if (!item.identity.work.trim()) return '';
  const preferences = item.titlePreferences;
  const work = [preferences?.includeGenre === false ? '' : item.genre.trim(), item.identity.work.trim()].filter(Boolean).join(' ');
  return [work, preferences?.includeComposer === false ? '' : item.identity.composer.trim(), preferences?.includeArranger !== false && item.identity.arranger.trim() ? `Arr. ${item.identity.arranger.trim()}` : '', preferences?.includeEnsemble === false ? '' : item.ensemble.trim()].filter(Boolean).join(` ${preferences?.separator || '—'} `);
}
