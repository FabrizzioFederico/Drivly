export const ars = (n) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(n ?? 0);

export const hora = (iso) =>
  iso ? new Date(iso).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit', hour12: false }) : '—';

/** 1600000 -> "1.600.000" (para campos con el $ aparte). */
export const miles = (n) => new Intl.NumberFormat('es-AR', { maximumFractionDigits: 2 }).format(n ?? 0);

export const CATEGORIA_LABEL = { AUTO: 'Auto', MOTO: 'Moto', CAMIONETA: 'Camioneta' };
