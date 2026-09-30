export function composeUploadTitle(item: { genre: string; ensemble: string; identity: { work: string; composer: string; arranger: string } }): string {
  if (!item.identity.work.trim()) return '';
  const work = [item.genre.trim(), item.identity.work.trim()].filter(Boolean).join(' ');
  return [work, item.identity.composer.trim(), item.identity.arranger.trim() ? `Arr. ${item.identity.arranger.trim()}` : '', item.ensemble.trim()].filter(Boolean).join(' — ');
}
