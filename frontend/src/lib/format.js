export const ars = (n) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(n ?? 0);

export const hora = (iso) =>
  iso ? new Date(iso).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', hour12: false }) : '—';

export const toLocalInput = (d) => {
  const pad = (x) => String(x).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

export function downloadCsv(filename, rows, columns) {
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const csv = [columns.map((c) => esc(c.label)).join(','), ...rows.map((r) => columns.map((c) => esc(c.value(r))).join(','))].join('\n');
  const url = URL.createObjectURL(new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' }));
  const a = Object.assign(document.createElement('a'), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}

export const fecha = (iso) =>
  iso ? new Date(iso).toLocaleDateString('es-AR', { weekday: 'short', day: 'numeric', month: 'short' }) : '—';

export const MODALIDADES = [
  { id: 'HORA', label: 'Por hora' },
  { id: 'SEMANAL', label: 'Semanal' },
  { id: 'MENSUAL', label: 'Mensual' },
  { id: 'ANUAL', label: 'Anual' },
];

export const CATEGORIA_LABEL = { AUTO: 'Auto', MOTO: 'Moto', CAMIONETA: 'Camioneta' };

/** Fin de un abono a partir de su inicio (el backend hace el mismo cálculo). */
export function finDeAbono(inicio, modalidad) {
  const f = new Date(inicio);
  if (modalidad === 'SEMANAL') return new Date(f.getTime() + 7 * 864e5);
  if (modalidad === 'MENSUAL') { f.setMonth(f.getMonth() + 1); return f; }
  if (modalidad === 'ANUAL') { f.setFullYear(f.getFullYear() + 1); return f; }
  return null;
}
