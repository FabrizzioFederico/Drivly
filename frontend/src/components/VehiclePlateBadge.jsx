/**
 * Formatea patentes argentinas:
 *  Mercosur auto  AA123BB -> AA 123 BB
 *  Mercosur moto  A123BCD -> A 123 BCD
 *  Formato viejo  ABC123  -> ABC 123
 */
export function formatPatente(raw = '') {
  const p = raw.replace(/[\s-]/g, '').toUpperCase();
  let m;
  if ((m = p.match(/^([A-Z]{2})(\d{3})([A-Z]{2})$/))) return `${m[1]} ${m[2]} ${m[3]}`;
  if ((m = p.match(/^([A-Z])(\d{3})([A-Z]{3})$/))) return `${m[1]} ${m[2]} ${m[3]}`;
  if ((m = p.match(/^([A-Z]{3})(\d{3})$/))) return `${m[1]} ${m[2]}`;
  return p;
}

export const isPatenteValida = (raw = '') =>
  /^([A-Z]{2}\d{3}[A-Z]{2}|[A-Z]\d{3}[A-Z]{3}|[A-Z]{3}\d{3})$/.test(raw.replace(/[\s-]/g, '').toUpperCase());

const SIZES = {
  sm: 'text-sm px-2 py-0.5 border-[1.5px] rounded-md',
  md: 'text-lg px-2.5 py-1 border-2 rounded-lg',
  lg: 'text-2xl px-3 py-1 border-2 rounded-lg',
};

export default function VehiclePlateBadge({ patente, size = 'md', dark = false, className = '' }) {
  return (
    <span
      className={`inline-block shrink-0 whitespace-nowrap font-mono font-bold tracking-[0.06em] ${SIZES[size]} ${dark ? 'border-white text-white' : 'border-ink text-ink'} ${className}`}
      aria-label={`Patente ${patente}`}
    >
      {formatPatente(patente)}
    </span>
  );
}
