export const ars = (n) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(n ?? 0);

export const hora = (iso) =>
  iso ? new Date(iso).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', hour12: false }) : '—';

export function downloadCsv(filename, rows, columns) {
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const csv = [columns.map((c) => esc(c.label)).join(','), ...rows.map((r) => columns.map((c) => esc(c.value(r))).join(','))].join('\n');
  const url = URL.createObjectURL(new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' }));
  const a = Object.assign(document.createElement('a'), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}

export const CATEGORIA_LABEL = { AUTO: 'Auto', MOTO: 'Moto', CAMIONETA: 'Camioneta' };
