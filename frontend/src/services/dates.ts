/** Database timestamps without an offset are stored in UTC. */
export function formatStoredDate(value: string | undefined): string {
  if (!value) return 'Data indisponível';
  const date = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : value + 'Z');
  return Number.isNaN(date.getTime()) ? 'Data indisponível' : date.toLocaleString('pt-BR');
}
