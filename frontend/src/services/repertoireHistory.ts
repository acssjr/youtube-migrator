interface CatalogEvent { name: string; project: string; performed_at: string; ensemble: string; venue: string }
export interface CatalogItem { id: string; title: string; work: string; composer: string; arranger: string; genre: string; ensemble: string; published_at: string; events: CatalogEvent[] }
interface RepertoireGroup { key: string; ensemble: string; work: string; composer: string; arranger: string; genre: string; recordings: CatalogItem[]; performedDates: string[]; publishedDates: string[] }
const normalized = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').replace(/\s+/g, ' ').trim();

export function groupRepertoire(items: CatalogItem[]): RepertoireGroup[] {
  const groups = new Map<string, RepertoireGroup>();
  for (const item of items) {
    const registeredEnsembles = item.events.map(event => event.ensemble).filter(Boolean);
    const ensembles = [...new Map((registeredEnsembles.length ? registeredEnsembles : [item.ensemble || 'Filarmônica não identificada']).map(value => [normalized(value), value])).values()];
    for (const ensemble of ensembles) {
      // Missing authors are not evidence that similarly named works are identical.
      const key = JSON.stringify([ensemble, item.work, item.composer, item.arranger].map(normalized).concat(item.composer ? [] : [item.id]));
      let group = groups.get(key);
      if (!group) {
        group = { key, ensemble, work: item.work, composer: item.composer, arranger: item.arranger, genre: item.genre, recordings: [], performedDates: [], publishedDates: [] };
        groups.set(key, group);
      }
      if (!group.recordings.some(record => record.id === item.id)) group.recordings.push(item);
      for (const event of item.events) {
        if (event.performed_at && (!event.ensemble || normalized(event.ensemble) === normalized(ensemble))) group.performedDates.push(event.performed_at.slice(0, 10));
      }
      if (item.published_at) group.publishedDates.push(item.published_at.slice(0, 10));
    }
  }
  return [...groups.values()].map(group => ({ ...group, performedDates: [...new Set(group.performedDates)].sort(), publishedDates: [...new Set(group.publishedDates)].sort(), recordings: group.recordings.sort((a, b) => b.published_at.localeCompare(a.published_at)) }));
}
