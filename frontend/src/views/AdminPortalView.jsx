import { useEffect, useMemo, useState } from 'react';
import { garajesService } from '../api/garajesService';
import { reservasService } from '../api/reservasService';
import StatusBadge from '../components/StatusBadge';
import VehiclePlateBadge, { formatPatente } from '../components/VehiclePlateBadge';
import { ars, downloadCsv, hora, CATEGORIA_LABEL } from '../lib/format';

const GARAJE_ID = Number(import.meta.env.VITE_DEFAULT_GARAJE_ID || 1);
const NAV = [
  { id: 'garaje', label: 'Mi Garaje' },
  { id: 'tarifas', label: 'Capacidad y Tarifas' },
  { id: 'equipo', label: 'Equipo (Playeros)' },
  { id: 'reportes', label: 'Reportes y Caja' },
];
const FILTROS = ['TODOS', 'HOLD', 'CONFIRMADA', 'EN_CURSO', 'CON_DEUDA', 'SIN_LUGAR'];
const STRIPES = 'repeating-linear-gradient(135deg,#7A8496 0 3px,#C9CFD8 3px 6px)';

function Kpis({ m }) {
  if (!m) return <div className="grid grid-cols-3 gap-4">{[0, 1, 2].map((i) => <div key={i} className="card h-[110px] animate-pulse" />)}</div>;
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <div className="card flex flex-col gap-1.5 px-5 py-4">
        <span className="text-[13px] font-semibold text-ink-muted">Ocupación pico del día</span>
        <div className="flex items-baseline gap-2.5"><span className="text-[34px] font-extrabold tracking-tight">{Math.round(m.ocupacion_pico * 100)}%</span><span className="text-[13px] text-ink-muted">{m.ocupacion_pico_lugares} lugares · {m.ocupacion_pico_hora}</span></div>
        <div className="h-1.5 overflow-hidden rounded-full bg-ink-soft"><div className={`h-full ${m.ocupacion_pico >= 0.9 ? 'bg-hold' : 'bg-success'}`} style={{ width: `${m.ocupacion_pico * 100}%` }} /></div>
      </div>
      <div className="card flex flex-col gap-1.5 px-5 py-4">
        <span className="text-[13px] font-semibold text-ink-muted">Reservas confirmadas hoy</span>
        <div className="flex items-baseline gap-2.5"><span className="text-[34px] font-extrabold tracking-tight">{m.reservas_confirmadas}</span><span className="text-[13px] font-bold text-success-ink">{m.reservas_variacion >= 0 ? '+' : ''}{m.reservas_variacion} vs. semana anterior</span></div>
        <span className="text-[13px] text-ink-muted">{m.en_hold} en HOLD ahora · {m.canceladas} canceladas</span>
      </div>
      <div className="card flex flex-col gap-1.5 px-5 py-4">
        <span className="text-[13px] font-semibold text-ink-muted">Recaudación total</span>
        <span className="text-[34px] font-extrabold tracking-tight">{ars(m.recaudacion_total)}</span>
        <span className="text-[13px] text-ink-muted">App {ars(m.recaudacion_app)} · Presencial {ars(m.recaudacion_presencial)} · Excedentes {ars(m.recaudacion_excedentes)}</span>
      </div>
    </div>
  );
}

function Stepper({ value, onChange, min = 0, max }) {
  return (
    <div className="flex items-center overflow-hidden rounded-card border-[1.5px] border-ink-line">
      <button onClick={() => onChange(Math.max(min, value - 1))} className="h-11 w-11 bg-[#F4F6F8] text-xl font-bold" aria-label="Restar">−</button>
      <input value={value} onChange={(e) => { const n = parseInt(e.target.value, 10); if (!Number.isNaN(n)) onChange(Math.min(max, Math.max(min, n))); }}
        className="w-14 text-center font-mono text-[17px] font-bold outline-none" inputMode="numeric" />
      <button onClick={() => onChange(Math.min(max, value + 1))} className="h-11 w-11 bg-[#F4F6F8] text-xl font-bold" aria-label="Sumar">+</button>
    </div>
  );
}

/* ---------- C1 · Capacidad y Tarifas (CU-06) ---------- */
const CATEGORIAS = ['AUTO', 'MOTO', 'CAMIONETA'];
const ABONOS = ['SEMANAL', 'MENSUAL', 'ANUAL'];
const MINIMOS = [15, 30, 60, 120]; // minutos mínimos cobrados = minimo_fracciones × 15
const SALIDAS = [60, 90, 120, 180, 240];
const minLabel = (m) => (m >= 60 ? `${m / 60} h` : `${m} min`);

/** Pasa de las filas del backend a la forma de los formularios. */
function desdeFilas(filas) {
  const hora = CATEGORIAS.map((categoria) => {
    const t = filas.find((f) => f.categoria === categoria && f.modalidad === 'HORA');
    return { categoria, precio_fraccion: t?.precio_fraccion ?? 0, minimo_min: (t?.minimo_fracciones ?? 1) * (t?.fraccion_min ?? 15) };
  });
  const abonos = Object.fromEntries(CATEGORIAS.map((c) => [c, Object.fromEntries(ABONOS.map((m) => {
    const t = filas.find((f) => f.categoria === c && f.modalidad === m);
    return [m, t?.precio_periodo ?? ''];
  }))]));
  return { hora, abonos };
}

/** Y de vuelta: una fila por categoría y modalidad. Un abono sin precio deja de ofrecerse. */
function aFilas({ hora, abonos }) {
  const filas = hora.map((h) => ({ categoria: h.categoria, modalidad: 'HORA', precio_fraccion: h.precio_fraccion, fraccion_min: 15, minimo_fracciones: h.minimo_min / 15, precio_periodo: null }));
  CATEGORIAS.forEach((c) => ABONOS.forEach((m) => {
    const precio = Number(abonos[c][m]);
    if (precio > 0) filas.push({ categoria: c, modalidad: m, precio_fraccion: null, fraccion_min: null, minimo_fracciones: null, precio_periodo: precio });
  }));
  return filas;
}

function TarifasPanel({ garajeId }) {
  const [garaje, setGaraje] = useState(null);
  const [config, setConfig] = useState(null);
  const [tarifas, setTarifas] = useState(null);
  const [metricas, setMetricas] = useState(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  const load = () => Promise.all([garajesService.get(garajeId), garajesService.getTarifas(garajeId), garajesService.metricas(garajeId)])
    .then(([g, t, m]) => {
      setGaraje(g);
      setConfig({ capacidad: g.capacidad, cupo_abonos: g.cupo_abonos, salida_estimada_default_min: g.salida_estimada_default_min, tolerancia_min: g.tolerancia_min, recargo_overstay: g.recargo_overstay });
      setTarifas(desdeFilas(t)); setMetricas(m); setMsg(null);
    })
    .catch((e) => setMsg({ ok: false, text: e.message }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [garajeId]);

  const set = (k, v) => setConfig((c) => ({ ...c, [k]: v, ...(k === 'capacidad' && c.cupo_abonos > v ? { cupo_abonos: v } : {}) }));
  const setHora = (i, k, v) => setTarifas((t) => ({ ...t, hora: t.hora.map((row, j) => (j === i ? { ...row, [k]: v } : row)) }));
  const setAbono = (c, m, v) => setTarifas((t) => ({ ...t, abonos: { ...t.abonos, [c]: { ...t.abonos[c], [m]: v } } }));

  const guardar = async () => {
    setSaving(true); setMsg(null);
    try {
      await Promise.all([garajesService.updateConfiguracion(garajeId, config), garajesService.updateTarifas(garajeId, aFilas(tarifas))]);
      setMsg({ ok: true, text: 'Cambios guardados. Aplican a reservas nuevas.' });
    } catch (e) { setMsg({ ok: false, text: e.message }); } finally { setSaving(false); }
  };

  if (!config || !tarifas) {
    return msg ? <div role="alert" className="rounded-card bg-debt-soft px-4 py-3 text-sm font-semibold text-debt-ink">{msg.text}</div>
      : <div className="card h-64 animate-pulse" />;
  }

  const auto = tarifas.hora.find((t) => t.categoria === 'AUTO');
  const pctAbonos = (config.cupo_abonos / (config.capacidad || 1)) * 100;
  const recargoPct = Math.round(config.recargo_overstay * 100);

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div><h1 className="text-[26px] font-extrabold tracking-tight">Capacidad y Tarifas</h1><p className="text-[13px] text-ink-muted">{garaje?.direccion}</p></div>
        <div className="flex gap-2.5">
          <button onClick={load} className="btn-outline">Descartar</button>
          <button onClick={guardar} disabled={saving || config.cupo_abonos > config.capacidad} className="btn-action">{saving ? 'Guardando…' : 'Guardar cambios'}</button>
        </div>
      </div>
      {msg && <div role="alert" className={`rounded-card px-4 py-3 text-sm font-semibold ${msg.ok ? 'bg-success-soft text-success-ink' : 'bg-debt-soft text-debt-ink'}`}>{msg.text}</div>}
      <Kpis m={metricas} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.55fr)]">
        <section className="card flex flex-col gap-4 p-[22px]">
          <div>
            <h2 className="text-[17px] font-extrabold">Capacidad</h2>
            <p className="text-[13px] text-ink-muted">Una sola capacidad para todos: conductores de la app, abonados y clientes sin reserva.</p>
          </div>
          <div className="flex items-center justify-between gap-3">
            <div><p className="text-sm font-bold">Lugares en Drivly</p><p className="text-xs text-ink-muted">Pueden ser menos que los físicos</p></div>
            <Stepper value={config.capacidad} min={1} max={2000} onChange={(v) => set('capacidad', v)} />
          </div>
          <div className="flex items-center justify-between gap-3">
            <div><p className="text-sm font-bold">Máximo para abonos</p><p className="text-xs text-ink-muted">Semanales, mensuales y anuales, sin lugar fijo</p></div>
            <Stepper value={config.cupo_abonos} max={config.capacidad} onChange={(v) => set('cupo_abonos', v)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="flex h-3.5 gap-0.5 overflow-hidden rounded-full">
              <div className="bg-brand-deep" style={{ width: `${pctAbonos}%` }} />
              <div className="flex-1 bg-brand" />
            </div>
            <div className="flex flex-wrap gap-x-3.5 text-xs font-semibold text-ink-muted">
              <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-brand-deep" />Hasta {config.cupo_abonos} para abonos</span>
              <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-brand" />El resto rota entre app y clientes sin reserva</span>
            </div>
          </div>
          <label className="flex items-center justify-between gap-3">
            <span><span className="block text-sm font-bold">Salida estimada sin reserva</span><span className="block text-xs text-ink-muted">Lo que el semáforo asume si el playero no indica otra</span></span>
            <select value={config.salida_estimada_default_min} onChange={(e) => set('salida_estimada_default_min', Number(e.target.value))} className="field w-28">
              {SALIDAS.map((m) => <option key={m} value={m}>{minLabel(m)}</option>)}
            </select>
          </label>

          <div className="h-px bg-ink-soft" />
          <h3 className="text-[15px] font-extrabold">Exceso de permanencia</h3>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1"><span className="text-xs font-bold text-ink-muted">Tolerancia</span>
              <div className="relative"><input type="number" min="0" value={config.tolerancia_min} onChange={(e) => set('tolerancia_min', Number(e.target.value))} className="field pr-12" /><span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-ink-muted">min</span></div>
            </label>
            <label className="flex flex-col gap-1"><span className="text-xs font-bold text-ink-muted">Recargo</span>
              <div className="relative"><input type="number" min="0" step="5" value={recargoPct} onChange={(e) => set('recargo_overstay', Number(e.target.value) / 100)} className="field pr-9" /><span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-ink-muted">%</span></div>
            </label>
          </div>
          <p className="mt-auto rounded-[10px] bg-[#F4F6F8] px-3 py-2.5 text-xs text-ink-muted">Los cambios aplican a reservas nuevas. Las reservas y abonos vigentes se respetan.</p>
        </section>

        <div className="flex min-w-0 flex-col gap-4">
          <section className="card flex flex-col gap-3.5 overflow-x-auto p-[22px]">
            <div className="flex items-baseline justify-between"><h2 className="text-[17px] font-extrabold">Tarifas por hora</h2><span className="text-xs text-ink-muted">Se cobra por fracción de 15 min</span></div>
            <table className="w-full min-w-[440px] border-separate border-spacing-x-2.5 border-spacing-y-1.5 text-left">
              <thead className="text-xs font-bold text-ink-muted"><tr><th>Categoría</th><th>Precio por fracción</th><th>Mínimo cobrado</th></tr></thead>
              <tbody>
                {tarifas.hora.map((t, i) => (
                  <tr key={t.categoria}>
                    <td className="text-sm font-bold">{CATEGORIA_LABEL[t.categoria]}</td>
                    <td><div className="relative"><span className="absolute left-3 top-1/2 -translate-y-1/2 font-bold text-ink-muted">$</span><input type="number" min="0" value={t.precio_fraccion} onChange={(e) => setHora(i, 'precio_fraccion', Number(e.target.value))} className="field pl-7" /></div></td>
                    <td><select value={t.minimo_min} onChange={(e) => setHora(i, 'minimo_min', Number(e.target.value))} className="field">{MINIMOS.map((m) => <option key={m} value={m}>{minLabel(m)}</option>)}</select></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="card flex flex-col gap-3.5 overflow-x-auto p-[22px]">
            <div><h2 className="text-[17px] font-extrabold">Abonos</h2><p className="text-[13px] text-ink-muted">Precio por período completo. Dejalo vacío si no ofrecés esa opción.</p></div>
            <table className="w-full min-w-[480px] border-separate border-spacing-x-1.5 border-spacing-y-1.5 text-left">
              <thead className="text-xs font-bold text-ink-muted"><tr><th>Categoría</th><th>Semanal</th><th>Mensual</th><th>Anual</th></tr></thead>
              <tbody>
                {CATEGORIAS.map((c) => (
                  <tr key={c}>
                    <td className="text-sm font-bold">{CATEGORIA_LABEL[c]}</td>
                    {ABONOS.map((m) => (
                      <td key={m}><div className="relative"><span className="absolute left-3 top-1/2 -translate-y-1/2 font-bold text-ink-muted">$</span>
                        <input type="number" min="0" placeholder="—" title="Vacío: no se ofrece" aria-label={`Abono ${m.toLowerCase()} ${CATEGORIA_LABEL[c]}`} value={tarifas.abonos[c][m]}
                          onChange={(e) => setAbono(c, m, e.target.value === '' ? '' : Number(e.target.value))} className="field pl-6 pr-2 text-[15px] placeholder:text-ink-subtle" />
                      </div></td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {auto && (
            <div className="flex flex-col gap-1.5 rounded-card bg-ink px-4 py-3.5 font-mono text-[13px] text-white">
              <span className="font-sans text-xs font-bold text-ink-subtle">Vista previa para el conductor</span>
              <div className="flex justify-between gap-3"><span>Auto · 3 h = 12 × {ars(auto.precio_fraccion)}</span><span className="font-bold">{ars(12 * auto.precio_fraccion)}</span></div>
              <div className="flex justify-between gap-3"><span>Overstay 30 min = 2 × {ars(auto.precio_fraccion)} + {recargoPct} %</span><span className="font-bold text-debt-light">{ars(Math.round(2 * auto.precio_fraccion * (1 + config.recargo_overstay)))}</span></div>
              {tarifas.abonos.AUTO.MENSUAL !== '' && <div className="flex justify-between gap-3"><span>Auto · abono mensual</span><span className="font-bold">{ars(tarifas.abonos.AUTO.MENSUAL)}</span></div>}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

/* ---------- C2 · Monitor en vivo y reportes (CU-10) ---------- */
function MonitorPanel({ garajeId }) {
  const [ocupacion, setOcupacion] = useState(null);
  const [reservas, setReservas] = useState([]);
  const [filtro, setFiltro] = useState('TODOS');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = () => garajesService.ocupacion(garajeId).then(setOcupacion).catch(() => {});
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [garajeId]);

  useEffect(() => {
    setLoading(true);
    reservasService.list({ garaje: garajeId }).then(setReservas).finally(() => setLoading(false));
  }, [garajeId]);

  const counts = useMemo(() => FILTROS.reduce((acc, f) => ({ ...acc, [f]: f === 'TODOS' ? reservas.length : reservas.filter((r) => r.estado === f).length }), {}), [reservas]);
  const filtradas = filtro === 'TODOS' ? reservas : reservas.filter((r) => r.estado === filtro);

  const exportar = () => downloadCsv(`drivly-reservas-${filtro.toLowerCase()}-${new Date().toISOString().slice(0, 10)}.csv`, filtradas, [
    { label: 'ID', value: (r) => r.id },
    { label: 'Patente', value: (r) => formatPatente(r.patente) },
    { label: 'Categoría', value: (r) => r.categoria },
    { label: 'Origen', value: (r) => r.origen },
    { label: 'Modalidad', value: (r) => r.modalidad },
    { label: 'Inicio', value: (r) => r.inicio },
    { label: 'Fin', value: (r) => r.fin },
    { label: 'Estado', value: (r) => r.estado },
    { label: 'Importe', value: (r) => r.total },
  ]);

  const total = ocupacion?.capacidad ?? 80;
  const umbral = Math.round(total * (ocupacion?.umbral_alerta ?? 0.9));
  const H = 220;
  const nowH = new Date().getHours();

  return (
    <>
      <div className="flex items-center justify-between">
        <div><h1 className="text-[26px] font-extrabold tracking-tight">Monitor de ocupación</h1><p className="text-[13px] text-ink-muted">{new Date().toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long' })}</p></div>
        <span className="inline-flex h-9 items-center gap-2 rounded-full bg-success-soft px-3.5 text-[13px] font-extrabold text-success-ink"><span className="h-2 w-2 animate-pulse rounded-full bg-success" />En vivo</span>
      </div>

      <section className="card flex flex-col gap-3.5 px-6 py-[22px]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h2 className="text-[17px] font-extrabold">Ocupación por franja horaria</h2><p className="text-[13px] text-ink-muted">Real hasta ahora · proyección según reservas confirmadas</p></div>
          <div className="flex gap-4 text-xs font-semibold text-ink-muted">
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-brand" />App y abonos</span>
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: STRIPES }} />Sin reserva</span>
            <span className="flex items-center gap-1.5"><span className="w-3.5 border-t-2 border-dashed border-hold" />Alerta {Math.round((ocupacion?.umbral_alerta ?? 0.9) * 100)}%</span>
          </div>
        </div>
        <div className="relative grid items-end gap-2 border-b-[1.5px] border-ink-line" style={{ height: H, gridTemplateColumns: `repeat(${ocupacion?.franjas.length ?? 18}, minmax(0,1fr))` }}>
          <div className="absolute inset-x-0 border-t-2 border-dashed border-hold" style={{ bottom: (umbral / total) * H }} />
          <span className="absolute right-0 bg-white pb-0.5 pl-1.5 text-[11px] font-bold text-hold-ink" style={{ bottom: (umbral / total) * H + 2 }}>{umbral} / {total}</span>
          {ocupacion?.franjas.map((f) => {
            const over = f.app + f.presencial >= umbral;
            return (
              <div key={f.hora} className="group relative flex h-full flex-col justify-end gap-0.5" style={{ opacity: f.proyectada ? 0.45 : 1 }}>
                <span className="pointer-events-none absolute -top-1 left-1/2 z-10 hidden -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-md bg-ink px-2 py-1 text-[11px] font-semibold text-white group-hover:block">
                  {f.hora}:00 · App y abonos {f.app} · Sin reserva {f.presencial}{over ? ' · ⚠' : ''}
                </span>
                <div className="rounded-t" style={{ height: (f.presencial / total) * H, background: STRIPES }} />
                <div className={`bg-brand ${f.hora === nowH ? 'outline outline-2 outline-offset-2 outline-ink' : ''}`} style={{ height: (f.app / total) * H }} />
              </div>
            );
          })}
        </div>
        <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${ocupacion?.franjas.length ?? 18}, minmax(0,1fr))` }}>
          {ocupacion?.franjas.map((f) => (
            <span key={f.hora} className={`text-center font-mono text-[11px] ${f.hora === nowH ? 'font-extrabold text-ink' : 'text-ink-subtle'}`}>{String(f.hora).padStart(2, '0')}</span>
          ))}
        </div>
      </section>

      <section className="card flex flex-col overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-[18px]">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="mr-2 text-[17px] font-extrabold">Reservas activas</h2>
            {FILTROS.map((f) => (
              <button key={f} onClick={() => setFiltro(f)} aria-pressed={filtro === f}
                className={`flex h-9 items-center gap-1.5 rounded-full border-[1.5px] px-3.5 text-xs font-bold tracking-wide ${filtro === f ? 'border-ink bg-ink text-white' : 'border-ink-line bg-white text-ink hover:border-ink-subtle'}`}>
                {f.replace('_', ' ')}<span className="opacity-70">{counts[f]}</span>
              </button>
            ))}
          </div>
          <button onClick={exportar} disabled={!filtradas.length} className="btn-outline min-h-[44px]">Exportar CSV</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead className="bg-[#F4F6F8] text-xs font-bold text-ink-muted">
              <tr>{['ID reserva', 'Patente', 'Categoría', 'Tipo', 'Horario', 'Estado', 'Importe'].map((h, i) => <th key={h} className={`px-6 py-2.5 ${i === 6 ? 'text-right' : ''}`}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {loading && <tr><td colSpan={7} className="px-6 py-6 text-ink-muted">Cargando reservas…</td></tr>}
              {!loading && !filtradas.length && <tr><td colSpan={7} className="px-6 py-6 text-ink-muted">No hay reservas con este estado.</td></tr>}
              {filtradas.map((r) => (
                <tr key={r.id} className="h-[52px] border-b border-ink-soft hover:bg-[#F8FAFF]">
                  <td className="px-6 font-mono text-[13px] text-ink-muted">{r.id}</td>
                  <td className="px-6"><VehiclePlateBadge patente={r.patente} size="sm" className="border-0 px-0" /></td>
                  <td className="px-6 text-xs font-extrabold tracking-wider">{r.categoria}</td>
                  <td className={`px-6 text-[13px] font-semibold ${r.origen === 'APP' ? 'text-brand-ink' : 'text-ink-muted'}`}>{r.origen !== 'APP' ? 'Sin reserva' : r.modalidad && r.modalidad !== 'HORA' ? `Abono ${r.modalidad.toLowerCase()}` : 'App'}</td>
                  <td className="px-6 font-semibold">{r.modalidad && !['HORA', 'PRESENCIAL'].includes(r.modalidad) ? `hasta ${new Date(r.fin).toLocaleDateString('es-AR')}` : `${hora(r.inicio)}–${hora(r.fin)}`}</td>
                  <td className="px-6"><StatusBadge estado={r.estado} /></td>
                  <td className="px-6 text-right font-extrabold">{ars(r.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function Placeholder({ title }) {
  return <div className="card flex h-64 items-center justify-center text-ink-muted">{title}: módulo pendiente de definición.</div>;
}

export default function AdminPortalView({ user }) {
  const garajeId = user?.garaje ?? GARAJE_ID;
  const [section, setSection] = useState('tarifas');

  return (
    <div className="mx-auto grid min-h-[800px] w-full max-w-[1440px] overflow-hidden rounded-sheet bg-paper shadow-2xl lg:grid-cols-[240px_1fr]">
      <aside className="flex flex-col gap-5 bg-ink px-3.5 py-5 text-white">
        <div className="flex items-center gap-2.5 px-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-brand text-[17px] font-extrabold">D</span>
          <span className="text-lg font-extrabold">Drivly</span>
          <span className="ml-auto text-[11px] font-bold text-ink-subtle">ADMIN</span>
        </div>
        <nav className="flex gap-1 overflow-x-auto lg:flex-col">
          {NAV.map((n) => (
            <button key={n.id} onClick={() => setSection(n.id)} aria-current={section === n.id ? 'page' : undefined}
              className={`flex min-h-touch shrink-0 items-center rounded-card px-3.5 text-left text-sm ${section === n.id ? 'bg-brand/25 font-bold text-white shadow-[inset_3px_0_0_#0066FF]' : 'font-semibold text-ink-subtle hover:bg-ink-800'}`}>
              {n.label}
            </button>
          ))}
        </nav>
        <div className="mt-auto hidden items-center gap-2.5 px-2 lg:flex">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-ink-800 text-[13px] font-extrabold">{(user?.nombre ?? 'A').split(' ').map((w) => w[0]).join('').slice(0, 2)}</span>
          <div className="flex flex-col"><span className="text-[13px] font-bold">{user?.nombre ?? 'Administrador'}</span><span className="text-[11px] text-ink-subtle">Propietario</span></div>
        </div>
      </aside>
      <main className="flex min-w-0 flex-col gap-5 p-6 lg:px-8 lg:py-7">
        {section === 'tarifas' && <TarifasPanel garajeId={garajeId} />}
        {section === 'reportes' && <MonitorPanel garajeId={garajeId} />}
        {section === 'garaje' && <Placeholder title="Mi Garaje" />}
        {section === 'equipo' && <Placeholder title="Equipo (Playeros)" />}
      </main>
    </div>
  );
}
