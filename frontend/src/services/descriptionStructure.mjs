export const baseStructure = () => ({ mainName: 'Sociedade Filarmônica 25 de Março', mainInstagram: '', mainFollow: '', playlists: '' });
export function instagramUrl(value) {
  const input = value.trim();
  if (!input) return '';
  if (/^https?:\/\//i.test(input)) {
    const url = new URL(input);
    if (!['instagram.com', 'www.instagram.com'].includes(url.hostname) || url.username || url.password) throw new Error('Informe um Instagram válido.');
    return `https://www.instagram.com${url.pathname}`;
  }
  const handle = input.replace(/^@/, '');
  if (!/^[a-zA-Z0-9_.]+$/.test(handle)) throw new Error('Use o @usuario ou o link do Instagram.');
  return `https://www.instagram.com/${handle}/`;
}
export function initialVideoStructure(structure = {}) {
  return { ensemble: structure.ensemble || '', instagram: (structure.social_text||'').match(/https?:\/\/(?:www\.)?instagram\.com\/[^\s]+/i)?.[0]||'', socialText: structure.social_text || '', history: structure.history || '', archive: structure.ensemble || '', includeArchive: !!structure.ensemble, guest: !!structure.ensemble && !/25 de mar[çc]o/i.test(structure.ensemble), body: structure.body || '' };
}
export function followBlock(name, handle, exact) {
    if (!handle.trim()) return exact.trim();
    const link = instagramUrl(handle);
    if (!exact.trim()) return `Siga a ${name} nas suas redes sociais:\nInstagram: ${link}`;
    let text = exact.replace(/^([^\p{L}]*Siga\s+a\s+).+?(?=\s+(?:no|nas|em)\b)/iu, (_, prefix) => `${prefix}${name}`);
    if (/https?:\/\/(?:www\.)?instagram\.com\/[^\s]+/i.test(text)) return text.replace(/https?:\/\/(?:www\.)?instagram\.com\/[^\s]+/gi, link);
    text = text.replace(/^Instagram:[^\n]*$/gim, '').trim();
    return `${text}\nInstagram: ${link}`;
}
export function composeStructure(common, video) {
  const main = followBlock(common.mainName, common.mainInstagram, common.mainFollow);
  const guest = video.guest ? followBlock(video.ensemble, video.instagram, video.socialText) : '';
  if (video.includeArchive && !video.archive.trim()) throw new Error('Preencha a instituição do acervo ou desmarque esse bloco.');
  return [main, guest, video.body, video.includeArchive ? `© Esta partitura pertence ao acervo da ${video.archive.trim()}.` : '', video.history, common.playlists].filter(x => x?.trim()).join('\n\n');
}
