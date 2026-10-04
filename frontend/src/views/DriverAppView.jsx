import { useEffect, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { garajesService } from '../api/garajesService';
import { reservasService } from '../api/reservasService';
import { vehiculosService } from '../api/vehiculosService';
import StatusBadge from '../components/StatusBadge';
import HoldTimer from '../components/HoldTimer';
import CercanosList from '../components/CercanosList';
import VehiclePlateBadge, { isPatenteValida } from '../components/VehiclePlateBadge';
import { ars, hora, fecha, toLocalInput, MODALIDADES, CATEGORIA_LABEL, finDeAbono } from '../lib/format';

const DEFAULT_POS = { lat: -34.5889, lng: -58.4306 }; // Palermo, CABA

function defaultHorario() {
  const inicio = new Date(); inicio.setMinutes(Math.ceil(inicio.getMinutes() / 15) * 15, 0, 0);
  const fin = new Date(inicio.getTime() + 3 * 3600000);
  return { inicio, fin };
}

/** Para abonos el fin no se elige: sale de la modalidad. */
const finEfectivo = (horario, modalidad) => (modalidad === 'HORA' ? horario.fin : finDeAbono(horario.inicio, modalidad));

function ErrorBanner({ error, onClose }) {
  if (!error) return null;
  return (
    <div role="alert" className="flex items-start justify-between gap-3 rounded-card bg-debt-soft px-4 py-3 text-sm font-semibold text-debt-ink">
      <span>{error}</span>
      <button onClick={onClose} className="min-h-touch min-w-touch -m-3 font-bold" aria-label="Cerrar">×</button>
    </div>
  );
}

function ModalidadSelector({ value, onChange, disabled }) {
  return (
    <div className="grid grid-cols-4 gap-1 rounded-card bg-ink-soft p-1" role="radiogroup" aria-label="Tipo de reserva">
      {MODALIDADES.map((m) => (
        <button key={m.id} role="radio" aria-checked={value === m.id} disabled={disabled} onClick={() => onChange(m.id)}
          className={`min-h-[40px] rounded-[9px] text-xs font-bold ${value === m.id ? 'bg-white text-brand shadow-sm' : 'text-ink-muted'}`}>
          {m.label}
        </button>
      ))}
    </div>
  );
}

/* ---------- 1. Búsqueda y mapa ---------- */
function SearchStep({ horario, setHorario, modalidad, setModalidad, onSelect }) {
  const [garajes, setGarajes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pos, setPos] = useState(DEFAULT_POS);
  const [lleno, setLleno] = useState(null); // garaje lleno elegido -> mostrar cercanos
  const [cercanos, setCercanos] = useState(null);

  useEffect(() => {
    navigator.geolocation?.getCurrentPosition(
      (p) => setPos({ lat: p.coords.latitude, lng: p.coords.longitude }),
      () => {}, { timeout: 4000 }
    );
  }, []);

  const fin = finEfectivo(horario, modalidad);

  useEffect(() => {
    let alive = true;
    setLoading(true); setLleno(null);
    garajesService
      .disponibles({ ...pos, radio: 1000, modalidad, inicio: horario.inicio.toISOString(), fin: fin.toISOString() })
      .then((d) => alive && setGarajes(d))
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pos, horario, modalidad]);

  const elegir = (g) => {
    if (g.lugares_libres > 0) { onSelect(g); return; }
    // Garaje lleno: en vez de bloquearlo, ofrecer los cercanos con lugar (regla 6)
    setLleno(g); setCercanos(null);
    garajesService.cercanos(g.id, { modalidad, inicio: horario.inicio.toISOString(), fin: fin.toISOString() })
      .then(setCercanos).catch(() => setCercanos([]));
  };

  // Proyección simple lat/lng -> % del contenedor. Reemplazar por @vis.gl/react-google-maps en producción.
  const bounds = garajes.reduce((b, g) => ({
    minLat: Math.min(b.minLat, g.lat), maxLat: Math.max(b.maxLat, g.lat),
    minLng: Math.min(b.minLng, g.lng), maxLng: Math.max(b.maxLng, g.lng),
  }), { minLat: pos.lat, maxLat: pos.lat, minLng: pos.lng, maxLng: pos.lng });
  const project = (lat, lng) => ({
    left: `${12 + ((lng - bounds.minLng) / (bounds.maxLng - bounds.minLng || 1)) * 70}%`,
    top: `${30 + (1 - (lat - bounds.minLat) / (bounds.maxLat - bounds.minLat || 1)) * 25}%`,
  });

  return (
    <div className="relative flex h-full flex-col bg-[#18202E]">
      <div className="absolute inset-0" aria-label="Mapa de garajes">
        {garajes.map((g) => {
          const full = g.lugares_libres === 0;
          return (
            <button key={g.id} onClick={() => elegir(g)} className="absolute flex -translate-x-1/2 flex-col items-center" style={project(g.lat, g.lng)}>
              <span className={`flex min-h-[36px] items-center gap-1.5 rounded-full px-3 text-[13px] font-extrabold shadow-lg ${full ? 'bg-ink-700 text-ink-subtle' : 'bg-white text-ink'}`}>
                {!full && <span className={`h-2 w-2 rounded-full ${g.lugares_libres > 10 ? 'bg-success' : 'bg-hold'}`} />}
                {full ? 'Lleno' : ars(g.precio_desde)}
              </span>
              <span className={`-mt-1.5 h-2.5 w-2.5 rotate-45 ${full ? 'bg-ink-700' : 'bg-white'}`} />
            </button>
          );
        })}
        <span className="absolute left-[8%] top-[62%] flex h-10 w-10 items-center justify-center rounded-full bg-brand/25">
          <span className="h-4 w-4 rounded-full border-[3px] border-white bg-brand" />
        </span>
      </div>

      <div className="relative z-10 flex flex-col gap-2 p-4">
        <div className="card flex flex-col gap-2.5 p-3">
          <ModalidadSelector value={modalidad} onChange={setModalidad} />
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 px-1 text-sm">
            <span className="h-3 w-3 shrink-0 rounded-full border-[2.5px] border-brand" />
            <input type="datetime-local" aria-label={modalidad === 'HORA' ? 'Ingreso' : 'Inicio del abono'} className="bg-transparent font-semibold"
              value={toLocalInput(horario.inicio)}
              onChange={(e) => { const ini = new Date(e.target.value); setHorario((h) => ({ inicio: ini, fin: new Date(ini.getTime() + (h.fin - h.inicio)) })); }} />
            <span className="text-ink-muted">hasta</span>
            {modalidad === 'HORA' ? (
              <input type="time" aria-label="Egreso" className="bg-transparent font-semibold" value={toLocalInput(horario.fin).slice(11)}
                onChange={(e) => { const [hh, mm] = e.target.value.split(':'); const f = new Date(horario.inicio); f.setHours(hh, mm); if (f <= horario.inicio) f.setDate(f.getDate() + 1); setHorario((h) => ({ ...h, fin: f })); }} />
            ) : (
              <span className="font-semibold">{fecha(fin)}</span>
            )}
          </div>
          {modalidad !== 'HORA' && <p className="px-1 text-xs text-ink-muted">Cochera móvil: tenés lugar asegurado, sin un número de cochera fijo.</p>}
        </div>
      </div>

      <div className="relative z-10 mt-auto flex max-h-[58%] flex-col rounded-t-3xl bg-paper">
        <div className="mx-auto mt-2.5 h-1.5 w-10 rounded-full bg-ink-line" />
        <div className="flex items-baseline justify-between px-5 pb-3 pt-3.5">
          <h2 className="text-xl font-extrabold">{loading ? 'Buscando…' : lleno ? `${lleno.nombre} está lleno` : `${garajes.length} garajes cerca`}</h2>
          {lleno && <button onClick={() => setLleno(null)} className="text-sm font-bold text-brand">Ver todos</button>}
        </div>
        <div className="flex flex-col gap-2.5 overflow-y-auto px-4 pb-6">
          <ErrorBanner error={error} onClose={() => setError(null)} />
          {loading && [0, 1, 2].map((i) => <div key={i} className="card h-[88px] animate-pulse" />)}
          {!loading && lleno && (
            <CercanosList titulo="Estos garajes cercanos tienen lugar" cercanos={cercanos} loading={!cercanos} onElegir={onSelect} />
          )}
          {!loading && !lleno && !garajes.length && (
            <p className="card p-4 text-sm text-ink-muted">Ningún garaje cercano ofrece {modalidad === 'HORA' ? 'reservas por hora' : `abono ${modalidad.toLowerCase()}`}. Probá con otra modalidad.</p>
          )}
          {!loading && !lleno && garajes.map((g) => (
            <button key={g.id} onClick={() => elegir(g)} className="card flex gap-3 p-3.5 text-left transition hover:ring-2 hover:ring-brand">
              <div className="h-[60px] w-[60px] shrink-0 rounded-card bg-[repeating-linear-gradient(135deg,#E3E7EC_0_6px,#EEF1F4_6px_12px)]" />
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <span className="truncate text-[15px] font-bold">{g.nombre}</span>
                <span className="text-xs text-ink-muted">{g.direccion} · {g.distancia_m} m</span>
                <div className="mt-0.5 flex flex-wrap gap-1.5">
                  <span className={`flex h-6 items-center gap-1.5 rounded-full px-2 text-xs font-bold ${g.lugares_libres > 10 ? 'bg-success-soft text-success-ink' : g.lugares_libres ? 'bg-hold-soft text-hold-ink' : 'bg-ink-soft text-ink-muted'}`}>
                    {g.lugares_libres ? `${g.lugares_libres} libres` : 'Lleno · ver cercanos'}
                  </span>
                  {g.techado && <span className="flex h-6 items-center rounded-full bg-ink-soft px-2 text-xs font-semibold text-ink-muted">Techado</span>}
                  {g.abierto_24h && <span className="flex h-6 items-center rounded-full bg-ink-soft px-2 text-xs font-semibold text-ink-muted">24 h</span>}
                </div>
              </div>
              <div className="flex flex-col text-right"><span className="text-[11px] text-ink-muted">desde</span><span className="text-lg font-extrabold">{ars(g.precio_desde)}</span><span className="text-[11px] text-ink-muted">{g.precio_unidad}</span></div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ---------- Vehículo: la categoría sale del registro oficial (regla 3) ---------- */
const ESTADO_VEHICULO = {
  VALIDADO: null,
  PENDIENTE: 'Validando con el registro oficial',
  RECHAZADO: 'No figura en el registro oficial',
};

function VehiculoSelector({ value, onChange, disabled }) {
  const [vehiculos, setVehiculos] = useState(null);
  const [nueva, setNueva] = useState('');
  const [agregando, setAgregando] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    vehiculosService.list().then((vs) => {
      setVehiculos(vs);
      const primero = vs.find((v) => v.estado_validacion === 'VALIDADO');
      if (primero && !value) onChange(primero);
    }).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const agregar = async (e) => {
    e.preventDefault();
    setAgregando(true); setError(null);
    try {
      const v = await vehiculosService.create(nueva.replace(/[\s-]/g, '').toUpperCase());
      setVehiculos((vs) => [...vs, v]);
      setNueva('');
      if (v.estado_validacion === 'VALIDADO') onChange(v);
    } catch (err) { setError(err.fields?.patente?.[0] ?? err.message); } finally { setAgregando(false); }
  };

  const reintentar = async (id) => {
    const v = await vehiculosService.revalidar(id);
    setVehiculos((vs) => vs.map((x) => (x.id === id ? v : x)));
    if (v.estado_validacion === 'VALIDADO') onChange(v);
  };

  return (
    <section className="card flex flex-col gap-2.5 p-3.5">
      <span className="text-[13px] font-bold text-ink-muted">Vehículo</span>
      {!vehiculos && <div className="h-14 animate-pulse rounded-card bg-ink-soft" />}
      <div className="flex flex-col gap-2" role="radiogroup" aria-label="Vehículo">
        {vehiculos?.map((v) => {
          const ok = v.estado_validacion === 'VALIDADO';
          const elegido = value?.id === v.id;
          return (
            <div key={v.id} role="radio" aria-checked={elegido} aria-disabled={!ok || disabled} tabIndex={ok && !disabled ? 0 : -1}
              onClick={() => ok && !disabled && onChange(v)} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && ok && !disabled && onChange(v)}
              className={`flex min-h-[56px] items-center gap-3 rounded-card border-[1.5px] px-3 ${elegido ? 'border-brand bg-brand-soft' : 'border-ink-line'} ${ok && !disabled ? 'cursor-pointer' : 'opacity-70'}`}>
              <VehiclePlateBadge patente={v.patente} size="sm" />
              {ok ? (
                <span className="text-sm font-bold">{CATEGORIA_LABEL[v.categoria]}</span>
              ) : (
                <span className={`text-xs font-semibold ${v.estado_validacion === 'RECHAZADO' ? 'text-debt-ink' : 'text-hold-ink'}`}>{ESTADO_VEHICULO[v.estado_validacion]}</span>
              )}
              {v.estado_validacion === 'PENDIENTE' && (
                <button onClick={(e) => { e.stopPropagation(); reintentar(v.id); }} className="ml-auto text-xs font-bold text-brand">Reintentar</button>
              )}
            </div>
          );
        })}
      </div>
      {!disabled && (
        <form onSubmit={agregar} className="flex gap-2">
          <input value={nueva} onChange={(e) => setNueva(e.target.value.toUpperCase())} placeholder="Agregar patente" aria-label="Patente nueva"
            className="field min-w-0 flex-1 font-mono tracking-[0.06em]" maxLength={9} autoCapitalize="characters" />
          <button disabled={agregando || !isPatenteValida(nueva)} className="btn-outline">{agregando ? 'Validando…' : 'Agregar'}</button>
        </form>
      )}
      {error && <span role="alert" className="text-xs font-semibold text-debt-ink">{error}</span>}
      <p className="text-xs text-ink-muted">La categoría y la tarifa salen del registro oficial de la patente, no se eligen.</p>
    </section>
  );
}

/* ---------- 2. Reserva y Hold (CU-04) ---------- */
function HoldStep({ garaje, horario, modalidad, vehiculo, setVehiculo, onBack, onCambiarGaraje, onConfirmed }) {
  const [reserva, setReserva] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [cercanos, setCercanos] = useState(null);
  const [expired, setExpired] = useState(false);
  const fin = finEfectivo(horario, modalidad);

  const crearHold = async () => {
    setBusy(true); setError(null); setExpired(false); setCercanos(null);
    try {
      setReserva(await reservasService.createHold({
        garaje: garaje.id, vehiculo: vehiculo.id, modalidad,
        inicio: horario.inicio.toISOString(), fin: fin.toISOString(),
      }));
    } catch (e) {
      setError(e.message);
      if (e.code === 'SIN_CUPO') setCercanos(e.data?.cercanos ?? []);
    } finally { setBusy(false); }
  };

  const pagar = async () => {
    setBusy(true); setError(null);
    try { onConfirmed(await reservasService.pagar(reserva.id)); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  const volver = async () => {
    if (reserva?.estado === 'HOLD') reservasService.cancelar(reserva.id).catch(() => {});
    onBack();
  };

  const d = reserva?.desglose;
  const horas = Math.round(((fin - horario.inicio) / 3600000) * 10) / 10;
  const resumen = modalidad === 'HORA'
    ? [['Ingreso', hora(horario.inicio)], ['Egreso', hora(fin)], ['Duración', `${horas} h`]]
    : [['Desde', fecha(horario.inicio)], ['Hasta', fecha(fin)], ['Abono', MODALIDADES.find((m) => m.id === modalidad).label]];

  return (
    <div className="flex h-full flex-col bg-paper">
      <header className="flex h-14 shrink-0 items-center gap-2 px-2">
        <button onClick={volver} className="flex min-h-touch min-w-touch items-center justify-center text-2xl" aria-label="Volver">‹</button>
        <h1 className="text-lg font-extrabold">{modalidad === 'HORA' ? 'Confirmar reserva' : 'Confirmar abono'}</h1>
      </header>

      <div className="flex flex-1 flex-col gap-3 overflow-y-auto px-4 pb-4">
        {reserva && !expired && (
          <div className="flex items-center gap-4 rounded-sheet bg-ink p-4">
            <HoldTimer expiresAt={reserva.hold_expira_en} onExpire={() => { setExpired(true); setReserva(null); }} />
            <div className="flex flex-col gap-1.5">
              <StatusBadge estado="HOLD" variant="dark" className="self-start" />
              <span className="font-bold text-white">Tu lugar está retenido</span>
              <span className="text-[13px] leading-snug text-ink-subtle">Pagá antes de que termine el tiempo o el lugar se libera.</span>
            </div>
          </div>
        )}
        {expired && <ErrorBanner error="Pasaron los 5 minutos y el lugar se liberó. Podés volver a retenerlo." onClose={() => setExpired(false)} />}
        <ErrorBanner error={error} onClose={() => { setError(null); setCercanos(null); }} />
        {cercanos && <CercanosList titulo="Garajes cercanos con lugar en ese horario" cercanos={cercanos} onElegir={onCambiarGaraje} />}

        <section className="card flex flex-col gap-3 p-3.5">
          <div className="flex items-center gap-3">
            <div className="h-[52px] w-[52px] shrink-0 rounded-card bg-[repeating-linear-gradient(135deg,#E3E7EC_0_6px,#EEF1F4_6px_12px)]" />
            <div className="flex flex-col"><span className="font-bold">{garaje.nombre}</span><span className="text-xs text-ink-muted">{garaje.direccion}</span></div>
          </div>
          <div className="grid grid-cols-3 rounded-card bg-[#F4F6F8] px-3 py-2.5">
            {resumen.map(([k, v]) => (
              <div key={k} className="flex flex-col"><span className="text-[11px] font-semibold text-ink-muted">{k}</span><span className="font-extrabold">{v}</span></div>
            ))}
          </div>
        </section>

        <VehiculoSelector value={vehiculo} onChange={setVehiculo} disabled={!!reserva} />

        {d && (
          <section className="card flex flex-col gap-2 p-3.5 text-sm">
            {d.modalidad === 'HORA' ? (
              <>
                <Row k={`${d.fracciones} fracciones de ${d.fraccion_min} min × ${ars(d.precio_fraccion)}`} v={ars(d.subtotal)} />
                {d.minimo_aplicado && <Row k={`Mínimo de ${d.minimo_fracciones} fracciones`} v="Aplicado" vClass="text-hold-ink" />}
              </>
            ) : (
              <Row k={`Abono ${d.modalidad.toLowerCase()} · ${CATEGORIA_LABEL[reserva.categoria]}`} v={ars(d.precio_periodo)} />
            )}
            <Row k="Cargo de servicio" v={ars(d.cargo_servicio)} />
            <div className="h-px bg-ink-soft" />
            <div className="flex items-baseline justify-between"><span className="font-bold">Total</span><span className="text-2xl font-extrabold">{ars(reserva.total)}</span></div>
          </section>
        )}
      </div>

      <footer className="flex shrink-0 flex-col gap-2 border-t border-ink-soft bg-white px-4 pb-6 pt-3">
        {reserva ? (
          <button onClick={pagar} disabled={busy} className="btn-action min-h-[56px] text-[17px]">
            {busy ? 'Procesando pago…' : `Pagar ${ars(reserva.total)}`}
          </button>
        ) : (
          <button onClick={crearHold} disabled={busy || !vehiculo} className="btn-primary min-h-[56px] text-[17px]">
            {busy ? 'Reteniendo lugar…' : vehiculo ? 'Retener lugar por 5 min' : 'Elegí un vehículo validado'}
          </button>
        )}
        <span className="text-center text-xs text-ink-muted">Pago con Mercado Pago</span>
      </footer>
    </div>
  );
}

const Row = ({ k, v, vClass = '' }) => (
  <div className="flex justify-between gap-3"><span className="text-ink-muted">{k}</span><span className={`shrink-0 font-semibold ${vClass}`}>{v}</span></div>
);

/* ---------- 3. Ticket QR (CU-07 / CU-08) ---------- */
function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true); const off = () => setOnline(false);
    window.addEventListener('online', on); window.addEventListener('offline', off);
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off); };
  }, []);
  return online;
}

/**
 * El QR es estático y está firmado por el servidor: se descarga una vez y queda guardado,
 * así funciona en un subsuelo sin señal (RFM-09). La seguridad la dan la firma, el estado
 * de la reserva y el control de patente del playero, no un código que cambie.
 */
function TicketStep({ reserva, onBack }) {
  const cacheKey = `drivly.ticket.${reserva.id}`;
  const [qr, setQr] = useState(() => JSON.parse(localStorage.getItem(cacheKey) || 'null'));
  const online = useOnline();

  useEffect(() => {
    if (qr) return;
    reservasService.getQr(reserva.id)
      .then((data) => { setQr(data); localStorage.setItem(cacheKey, JSON.stringify(data)); })
      .catch(() => { /* sin conexión: se reintenta al volver a abrir el ticket */ });
  }, [qr, reserva.id, cacheKey]);

  const g = reserva.garaje_detalle;
  const mapsUrl = g ? `https://www.google.com/maps/dir/?api=1&destination=${g.lat},${g.lng}` : '#';
  const esAbono = reserva.modalidad && reserva.modalidad !== 'HORA';

  return (
    <div className="flex h-full flex-col bg-brand-deep">
      <header className="flex h-14 shrink-0 items-center justify-between px-2 text-white">
        <div className="flex items-center gap-2">
          <button onClick={onBack} className="flex min-h-touch min-w-touch items-center justify-center text-2xl" aria-label="Volver">‹</button>
          <h1 className="text-lg font-extrabold">{esAbono ? 'Mi abono' : 'Mi ticket'}</h1>
        </div>
        <span className="mr-3 flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1.5 text-xs font-bold">
          <span className={`h-2 w-2 rounded-full ${qr ? 'bg-action' : 'bg-hold'}`} />
          {qr ? (online ? 'Guardado en el teléfono' : 'Sin conexión · QR guardado') : 'Descargando QR…'}
        </span>
      </header>

      <div className="mx-5 mt-2 flex flex-col rounded-[20px] bg-white shadow-2xl">
        <div className="flex flex-col items-center gap-3.5 px-5 pb-4 pt-5">
          <div className="flex w-full items-center justify-between">
            <span className="text-[13px] font-bold text-ink-muted">QR de ingreso y egreso</span>
            <StatusBadge estado={reserva.estado} />
          </div>
          <div className="rounded-sheet border-[3px] border-action p-3">
            {qr ? <QRCodeSVG value={qr.qr_token} size={220} level="M" fgColor="#121824" /> : <div className="h-[220px] w-[220px] animate-pulse bg-ink-soft" />}
          </div>
          <p className="text-center text-[13px] font-semibold text-ink-muted">
            {esAbono
              ? `Mostralo en cada ingreso y egreso hasta el ${fecha(reserva.fin)}.`
              : 'Funciona sin señal. Mostralo al entrar y al salir.'}
          </p>
        </div>
        <div className="relative flex h-6 items-center">
          <span className="absolute -left-3 h-6 w-6 rounded-full bg-brand-deep" />
          <span className="absolute -right-3 h-6 w-6 rounded-full bg-brand-deep" />
          <span className="mx-5 flex-1 border-t-2 border-dashed border-ink-line" />
        </div>
        <div className="flex flex-col gap-3.5 px-5 pb-5 pt-3">
          <div className="flex items-center justify-between"><VehiclePlateBadge patente={reserva.patente} size="lg" /><span className="text-sm font-bold text-ink-muted">{CATEGORIA_LABEL[reserva.categoria]}</span></div>
          <div className="grid grid-cols-2 gap-2.5">
            <div className="flex flex-col"><span className="text-[11px] font-semibold text-ink-muted">{esAbono ? 'Desde' : 'Inicio'}</span><span className="text-[17px] font-extrabold">{esAbono ? fecha(reserva.inicio) : hora(reserva.inicio)}</span></div>
            <div className="flex flex-col"><span className="text-[11px] font-semibold text-ink-muted">{esAbono ? 'Hasta' : 'Fin'}</span><span className="text-[17px] font-extrabold">{esAbono ? fecha(reserva.fin) : hora(reserva.fin)}</span></div>
          </div>
          {g && <div className="flex flex-col"><span className="font-bold">{g.nombre}</span><span className="text-[13px] text-ink-muted">{g.direccion}</span></div>}
          <div className="flex justify-between text-xs text-ink-muted"><span>ID reserva</span><span className="font-mono font-bold text-ink">{reserva.id}</span></div>
        </div>
      </div>

      <div className="mt-auto grid grid-cols-[1fr_auto] gap-2.5 px-5 pb-7 pt-4">
        <a href={mapsUrl} target="_blank" rel="noreferrer" className="btn min-h-[56px] bg-white text-brand hover:text-brand-deep hover:no-underline">Abrir en Maps</a>
        <button onClick={() => navigator.share?.({ title: 'Mi reserva Drivly', text: `${reserva.id} · ${g?.nombre ?? ''}` })} className="btn-ghost-dark min-h-[56px] border-white/40">Compartir</button>
      </div>
    </div>
  );
}

/* ---------- Contenedor ---------- */
export default function DriverAppView() {
  const [step, setStep] = useState('search');
  const [garaje, setGaraje] = useState(null);
  const [reserva, setReserva] = useState(null);
  const [horario, setHorario] = useState(defaultHorario);
  const [modalidad, setModalidad] = useState('HORA');
  const [vehiculo, setVehiculo] = useState(null); // se conserva si cambia de garaje

  const elegirGaraje = (g) => { setGaraje(g); setStep('hold'); };

  return (
    <div className="mx-auto h-[844px] max-h-[calc(100vh-88px)] w-full max-w-[390px] overflow-hidden rounded-[32px] shadow-2xl">
      {step === 'search' && (
        <SearchStep horario={horario} setHorario={setHorario} modalidad={modalidad} setModalidad={setModalidad} onSelect={elegirGaraje} />
      )}
      {step === 'hold' && (
        <HoldStep key={garaje.id} garaje={garaje} horario={horario} modalidad={modalidad} vehiculo={vehiculo} setVehiculo={setVehiculo}
          onBack={() => setStep('search')} onCambiarGaraje={elegirGaraje}
          onConfirmed={(r) => { setReserva({ ...r, garaje_detalle: r.garaje_detalle ?? garaje }); setStep('ticket'); }} />
      )}
      {step === 'ticket' && <TicketStep reserva={reserva} onBack={() => setStep('search')} />}
    </div>
  );
}
