const COLORS = { verde: '#00E6A7', ambar: '#FF9F43', rojo: '#FF5252' };
const STRIPES = 'repeating-linear-gradient(135deg,#7A8496 0 3px,#4A5568 3px 6px)';
const PROXIMAS = 'repeating-linear-gradient(135deg,#0066FF 0 3px,transparent 3px 6px)';

/** Nivel según los lugares que pueden tomar clientes sin reserva. Rojo = no entra nadie más sin reserva. */
export function nivelPresencial(libresPresencial, capacidad) {
  if (libresPresencial <= 0) return 'rojo';
  if (capacidad && libresPresencial / capacidad <= 0.1) return 'ambar';
  return 'verde';
}

/**
 * Semáforo del playero (regla 6). App, abonos y presenciales comparten una única capacidad:
 * el número grande es cuántos clientes sin reserva pueden entrar ahora sin dejar sin lugar
 * a los conductores de la app que llegan dentro de la ventana.
 */
export default function TrafficLight({ ocupacion }) {
  if (!ocupacion) {
    return <div className="h-[120px] animate-pulse rounded-sheet border border-ink-700 bg-ink-900" />;
  }
  const { capacidad, libres, libres_presencial, ocupados_app, ocupados_presencial, ocupados_abonos = 0, proximas_app, ventana_min } = ocupacion;
  const nivel = nivelPresencial(libres_presencial, capacidad);
  const pct = (n) => `${(n / (capacidad || 1)) * 100}%`;

  return (
    <div className="flex items-center gap-4 rounded-sheet border border-ink-700 bg-ink-900 p-4"
      aria-label={`${libres_presencial} lugares para clientes sin reserva, ${libres} libres de ${capacidad}`}>
      <div className="flex shrink-0 flex-col gap-2 rounded-2xl bg-[#0B0F17] p-2">
        {['rojo', 'ambar', 'verde'].map((n) => (
          <span key={n} className="h-6 w-6 rounded-full transition-all"
            style={{ background: nivel === n ? COLORS[n] : '#2A3446', boxShadow: nivel === n ? `0 0 14px ${COLORS[n]}` : 'none' }} />
        ))}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="text-4xl font-extrabold leading-none" style={{ color: COLORS[nivel] }}>{libres_presencial}</span>
          <span className="text-sm font-semibold text-ink-subtle">
            {nivel === 'rojo' ? 'sin lugar para clientes sin reserva' : 'lugares para clientes sin reserva'}
          </span>
        </div>
        <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-full bg-ink-700">
          <div className="bg-brand" style={{ width: pct(ocupados_app + ocupados_abonos) }} />
          <div style={{ width: pct(ocupados_presencial), background: STRIPES }} />
          <div className="border border-brand" style={{ width: pct(Math.min(proximas_app, libres)), background: PROXIMAS }} />
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs font-semibold text-ink-subtle">
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-brand" />App y abonos {ocupados_app + ocupados_abonos}</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: STRIPES }} />Presencial {ocupados_presencial}</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm border border-brand" style={{ background: PROXIMAS }} />Llegan en {ventana_min / 60} h: {proximas_app}</span>
          <span>{libres} libres de {capacidad}</span>
        </div>
      </div>
    </div>
  );
}
