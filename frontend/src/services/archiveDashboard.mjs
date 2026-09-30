const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();
export function playlistIds(text) {
  const ids = new Set();
  for (const candidate of String(text || '').match(/https?:\/\/[^\s<>]+/g) || []) {
    try { const url = new URL(candidate.replace(/[),.;]+$/, '')); if (['youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'].includes(url.hostname) && url.searchParams.get('list')) ids.add(url.searchParams.get('list')); } catch { /* A malformed URL is not a playlist reference. */ }
  }
  return ids;
}
export function buildArchivePending(videos, records, channelId) {
  const scoped = records.filter(record => !record.payload.channel_id || record.payload.channel_id === channelId);
  const events = scoped.filter(record => record.kind === 'event');
  const originals = scoped.filter(record => record.kind === 'original');
  const originalIds = new Set(originals.flatMap(record => (Array.isArray(record.payload.files) ? record.payload.files : []).map(file => file?.videoId).filter(Boolean)));
  const footers = scoped.filter(record => record.kind === 'footer').sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  const outdated = videos.filter(video => {
    if (!video.description.trim()) return false;
    const ensembles = [video.ensemble, ...video.events.map(event => event.ensemble)].filter(Boolean).map(normalize);
    const projects = video.events.flatMap(event => [event.name, event.project]).filter(Boolean).map(normalize);
    const compatible = footers.filter(record => (!record.payload.ensemble || ensembles.includes(normalize(record.payload.ensemble))) && (!record.payload.project || projects.includes(normalize(record.payload.project))));
    const footer = compatible.find(record => record.payload.ensemble) || compatible[0];
    if (!footer) return false;
    const expected = playlistIds(footer.payload.text), actual = playlistIds(video.description);
    return expected.size > 0 && [...expected].some(id => !actual.has(id));
  });
  const backups = scoped.filter(record => record.kind === 'backup').sort((a, b) => b.created_at.localeCompare(a.created_at));
  return {
    blank: videos.filter(video => !video.description.trim()),
    credits: videos.filter(video => !video.composer.trim() || !video.work.trim()),
    ambiguous: videos.filter(video => video.catalog_ambiguous),
    undated: events.filter(record => !String(record.payload.performed_at || '').trim()),
    outdated,
    originals: originals.length ? videos.filter(video => !originalIds.has(video.id)) : null,
    originalCount: videos.filter(video => originalIds.has(video.id)).length,
    approvedCount: scoped.filter(record => record.kind === 'approved_text' && record.payload.approved === true).length,
    latestBackup: backups[0] || null,
  };
}
