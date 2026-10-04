import { ars } from '../lib/format';

/**
 * Garajes con lugar cerca de uno que no tiene (regla 6).
 * La usan el conductor (fondo claro) y el playero (fondo oscuro) para derivar.
 */
export default function CercanosList({ cercanos, titulo, onElegir, dark = false, loading = false }) {
  const base = dark ? 'bg-ink-900 border border-ink-700' : 'card';
  const muted = dark ? 'text-ink-subtle' : 'text-ink-muted';

  return (
    <section className={`${base} flex flex-col gap-2.5 rounded-sheet p-3.5`} aria-live="polite">
      <h3 className="text-[15px] font-extrabold">{titulo}</h3>
      {loading && <span className={`text-sm ${muted}`}>Buscando garajes con lugar…</span>}
      {!loading && !cercanos?.length && (
        <span className={`text-sm ${muted}`}>No hay garajes Drivly con lugar en 1 km. Probá con otro horario.</span>
      )}
      {!loading && cercanos?.map((g) => {
        const contenido = (
          <>
            <div className="flex min-w-0 flex-1 flex-col">
              <span className="truncate font-bold">{g.nombre}</span>
              <span className={`text-xs ${muted}`}>{g.direccion} · a {g.distancia_m} m</span>
            </div>
            <div className="flex shrink-0 flex-col items-end">
              <span className={`text-sm font-extrabold ${dark ? 'text-action' : 'text-success-ink'}`}>{g.lugares_libres} libres</span>
              {g.precio_desde != null && <span className={`text-xs ${muted}`}>desde {ars(g.precio_desde)} {g.precio_unidad}</span>}
            </div>
          </>
        );
        return onElegir ? (
          <button key={g.id} onClick={() => onElegir(g)}
            className={`flex min-h-touch items-center gap-3 rounded-card px-3 py-2 text-left transition ${dark ? 'bg-ink hover:bg-ink-800' : 'bg-[#F4F6F8] hover:ring-2 hover:ring-brand'}`}>
            {contenido}
          </button>
        ) : (
          <div key={g.id} className={`flex min-h-touch items-center gap-3 rounded-card px-3 py-2 ${dark ? 'bg-ink' : 'bg-[#F4F6F8]'}`}>{contenido}</div>
        );
      })}
    </section>
  );
}
