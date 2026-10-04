import { useCallback, useEffect, useRef, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { garajesService } from '../api/garajesService';
import { operacionService } from '../api/operacionService';
import TrafficLight from '../components/TrafficLight';
import CercanosList from '../components/CercanosList';
import StatusBadge from '../components/StatusBadge';
import VehiclePlateBadge, { isPatenteValida } from '../components/VehiclePlateBadge';
import { ars, hora } from '../lib/format';

const SALIDAS = [60, 120, 240];
const horasLabel = (m) => (m % 60 ? `${m} min` : `${m / 60} h`);

const GARAJE_ID = Number(import.meta.env.VITE_DEFAULT_GARAJE_ID || 1);

/**
 * Visor de cámara con BarcodeDetector nativo (Chrome/Android, Safari 17+).
 * Si el navegador no lo soporta, el playero usa el ingreso manual por patente o token.
 */
function QrViewfinder({ active, onScan }) {
  const videoRef = useRef(null);
  const [status, setStatus] = useState('idle'); // idle | running | unsupported | denied

  useEffect(() => {
    if (!active) return undefined;
    if (!('BarcodeDetector' in window) || !navigator.mediaDevices?.getUserMedia) { setStatus('unsupported'); return undefined; }
    let stream; let raf; let stopped = false;
    const detector = new window.BarcodeDetector({ formats: ['qr_code'] });

    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
      .then((s) => {
        stream = s;
        videoRef.current.srcObject = s;
        return videoRef.current.play();
      })
      .then(() => {
        setStatus('running');
        const tick = async () => {
          if (stopped) return;
          try {
            const codes = await detector.detect(videoRef.current);
            if (codes[0]?.rawValue) { onScan(codes[0].rawValue); return; }
          } catch { /* frame no listo */ }
          raf = requestAnimationFrame(tick);
        };
        tick();
      })
      .catch(() => setStatus('denied'));

    return () => { stopped = true; cancelAnimationFrame(raf); stream?.getTracks().forEach((t) => t.stop()); };
  }, [active, onScan]);

  const corner = 'absolute h-9 w-9 border-action';
  return (
    <div className="relative h-[250px] shrink-0 overflow-hidden rounded-sheet bg-[repeating-linear-gradient(135deg,#161D2A_0_10px,#1A2230_10px_20px)]">
      <video ref={videoRef} muted playsInline className={`absolute inset-0 h-full w-full object-cover ${status === 'running' ? '' : 'hidden'}`} />
      <span className={`${corner} left-[70px] top-10 rounded-tl-lg border-l-4 border-t-4`} />
      <span className={`${corner} right-[70px] top-10 rounded-tr-lg border-r-4 border-t-4`} />
      <span className={`${corner} bottom-10 left-[70px] rounded-bl-lg border-b-4 border-l-4`} />
      <span className={`${corner} bottom-10 right-[70px] rounded-br-lg border-b-4 border-r-4`} />
      {active && status !== 'unsupported' && status !== 'denied' && <span className="absolute left-[60px] right-[60px] h-0.5 animate-scan bg-action shadow-[0_0_12px_#00E6A7]" />}
      <p className="absolute inset-x-0 bottom-2.5 px-4 text-center text-[13px] font-bold text-white">
        {!active && 'Elegí qué vas a escanear'}
        {active && status === 'running' && 'Apuntá al QR del conductor'}
        {active && status === 'unsupported' && 'Este navegador no soporta escaneo. Usá ingreso manual.'}
        {active && status === 'denied' && 'Sin permiso de cámara. Usá ingreso manual.'}
      </p>
    </div>
  );
}

/* ---------- Modal de deuda por overstay (CU-08) ---------- */
function OverstayModal({ deuda, onClose }) {
  const [pagado, setPagado] = useState(null);
  const [busy, setBusy] = useState(false);

  // Polling del estado de pago de Mercado Pago (cada 3 s)
  useEffect(() => {
    if (pagado) return undefined;
    const id = setInterval(async () => {
      try { const r = await operacionService.estadoDeuda(deuda.reserva_id); if (r.pagado) setPagado({ medio: 'Mercado Pago', tx: r.transaccion_id }); } catch { /* reintenta */ }
    }, 3000);
    return () => clearInterval(id);
  }, [deuda.reserva_id, pagado]);

  const efectivo = async () => {
    setBusy(true);
    try { await operacionService.registrarEfectivo(deuda.reserva_id); setPagado({ medio: 'Efectivo' }); } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 sm:items-center" role="dialog" aria-modal="true" aria-labelledby="overstay-title">
      <div className="flex max-h-[95vh] w-full max-w-[420px] flex-col gap-3 overflow-y-auto rounded-t-3xl border-t-4 border-debt bg-ink-900 p-5 text-white sm:rounded-3xl">
        <div className="flex items-center justify-between">
          <StatusBadge estado="CON_DEUDA" variant="dark" />
          <VehiclePlateBadge patente={deuda.patente} dark />
        </div>
        <div>
          <p id="overstay-title" className="text-sm font-semibold text-ink-subtle">Estadía excedida</p>
          <p className="flex items-baseline gap-2"><span className="text-5xl font-extrabold tracking-tight text-debt-light">+{deuda.minutos_excedidos} min</span><span className="text-[13px] font-semibold text-ink-subtle">sobre tolerancia</span></p>
        </div>
        <div className="grid grid-cols-3 gap-1.5 rounded-card bg-ink px-3 py-2.5">
          <div className="flex flex-col"><span className="text-[11px] font-semibold text-ink-subtle">Reserva hasta</span><span className="font-extrabold">{hora(deuda.fin_reservado)}</span></div>
          <div className="flex flex-col"><span className="text-[11px] font-semibold text-ink-subtle">Tolerancia</span><span className="font-extrabold">+{deuda.tolerancia_min} min</span></div>
          <div className="flex flex-col"><span className="text-[11px] font-semibold text-ink-subtle">Egreso real</span><span className="font-extrabold text-debt-light">{hora(deuda.egreso_real)}</span></div>
        </div>
        <div className="rounded-card border border-ink-700 bg-ink p-3 font-mono text-[13px] leading-relaxed text-ink-subtle">
          <div>⌈{deuda.minutos_excedidos} min ÷ {deuda.fraccion_min ?? 15}⌉ = {deuda.fracciones} fracciones</div>
          <div>{deuda.fracciones} × {ars(deuda.precio_fraccion)} + {Math.round(deuda.recargo * 100)} % de recargo</div>
          <div className="mt-1.5 flex justify-between border-t border-ink-700 pt-1.5 font-bold text-white"><span>Total a cobrar</span><span className="text-xl">{ars(deuda.total)}</span></div>
        </div>

        {!pagado ? (
          <>
            <div className="flex items-center gap-3.5 rounded-[14px] bg-white p-3 text-ink">
              <QRCodeSVG value={deuda.mp_qr_data} size={124} level="M" />
              <div className="flex flex-col gap-1.5">
                <span className="font-extrabold">QR Mercado Pago</span>
                <span className="text-xs leading-snug text-ink-muted">El conductor escanea y paga {ars(deuda.total)} desde su app.</span>
                <span className="flex items-center gap-1.5 text-xs font-bold text-hold-ink"><span className="h-2 w-2 animate-pulse rounded-full bg-hold" />Esperando pago…</span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              <button onClick={efectivo} disabled={busy} className="btn-ghost-dark min-h-[64px]">Cobro en efectivo</button>
              <button onClick={async () => { const r = await operacionService.estadoDeuda(deuda.reserva_id); if (r.pagado) setPagado({ medio: 'Mercado Pago', tx: r.transaccion_id }); }} className="btn-primary min-h-[64px]">Verificar pago</button>
            </div>
          </>
        ) : (
          <>
            <div className="flex flex-col items-center gap-2 rounded-[14px] border-[1.5px] border-action bg-action/10 px-3 py-5">
              <span className="text-[13px] font-extrabold tracking-wider text-action">PAGO ACREDITADO</span>
              <span className="text-xl font-extrabold">{ars(deuda.total)} · {pagado.medio}</span>
              {pagado.tx && <span className="font-mono text-xs text-ink-subtle">TX {pagado.tx}</span>}
            </div>
            <button onClick={onClose} className="btn-action min-h-[72px] text-lg">Liberar salida</button>
          </>
        )}
      </div>
    </div>
  );
}

/* ---------- Vista principal del playero ---------- */
export default function ValetPortalView({ user }) {
  const garajeId = user?.garaje ?? GARAJE_ID;
  const [ocupacion, setOcupacion] = useState(null);
  const [mode, setMode] = useState(null); // 'ingreso' | 'egreso'
  const [manual, setManual] = useState('');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [deuda, setDeuda] = useState(null);
  const [movs, setMovs] = useState([]);
  const [salidaMin, setSalidaMin] = useState(null); // salida estimada del cliente sin reserva
  const [derivar, setDerivar] = useState(null); // { titulo, detalle?, cercanos } (regla 6)

  const loadOcupacion = useCallback(() => garajesService.ocupacion(garajeId).then(setOcupacion).catch(() => {}), [garajeId]);
  useEffect(() => { loadOcupacion(); const id = setInterval(loadOcupacion, 10000); return () => clearInterval(id); }, [loadOcupacion]);

  const ventana = salidaMin ?? ocupacion?.ventana_min ?? 120;
  const sinLugarPresencial = ocupacion && ocupacion.libres_presencial <= 0;

  const mostrarCercanos = useCallback((titulo, detalle, cercanos) => {
    setDerivar({ titulo, detalle, cercanos: cercanos ?? null });
    if (!cercanos) garajesService.cercanos(garajeId).then((c) => setDerivar((d) => d && { ...d, cercanos: c })).catch(() => setDerivar((d) => d && { ...d, cercanos: [] }));
  }, [garajeId]);

  const procesar = useCallback(async (payload) => {
    if (!mode || busy) return;
    setFeedback(null); setDerivar(null);

    // Cliente sin reserva con el semáforo en rojo: no se registra, se deriva (regla 6)
    if (mode === 'ingreso' && payload.patente && sinLugarPresencial) {
      mostrarCercanos('Sin lugar para clientes sin reserva', 'Los lugares libres están comprometidos con conductores de la app. Indicale un garaje cercano:');
      return;
    }

    setBusy(true);
    try {
      const body = { garaje: garajeId, ...payload };
      if (mode === 'sin_lugar') {
        const res = await operacionService.sinLugar(body);
        setMovs((m) => [res.reserva, ...m.filter((x) => x.id !== res.reserva.id)].slice(0, 4));
        mostrarCercanos(
          `Reserva de ${res.reserva.patente} marcada sin lugar`,
          `Se pidió el reembolso de ${ars(res.reembolso.monto)} y el incidente quedó registrado. Indicale al conductor un garaje cercano:`,
          res.cercanos,
        );
      } else {
        if (mode === 'ingreso' && payload.patente) body.salida_estimada = new Date(Date.now() + ventana * 60000).toISOString();
        const res = mode === 'ingreso' ? await operacionService.ingreso(body) : await operacionService.egreso(body);
        setMovs((m) => [res.reserva, ...m.filter((x) => x.id !== res.reserva.id)].slice(0, 4));
        if (res.deuda) setDeuda(res.deuda);
        else setFeedback({ ok: true, text: mode === 'ingreso' ? 'Ingreso registrado. Barrera abierta.' : 'Egreso registrado. Salida liberada.' });
        if (res.ocupacion) setOcupacion(res.ocupacion); else loadOcupacion();
      }
      setMode(null); setManual(''); setSalidaMin(null);
    } catch (e) {
      if (e.code === 'SIN_LUGAR_PRESENCIAL') { mostrarCercanos('Sin lugar para clientes sin reserva', e.message, e.data?.cercanos); loadOcupacion(); }
      else setFeedback({ ok: false, text: e.message });
    } finally { setBusy(false); }
  }, [mode, busy, garajeId, loadOcupacion, sinLugarPresencial, mostrarCercanos, ventana]);

  const onScan = useCallback((token) => procesar({ qr_token: token }), [procesar]);

  const submitManual = (e) => {
    e.preventDefault();
    const v = manual.trim();
    if (!v) return;
    if (mode === 'sin_lugar' || !isPatenteValida(v)) procesar({ qr_token: v });
    else procesar({ patente: v.replace(/[\s-]/g, '').toUpperCase() });
  };

  return (
    <div className="mx-auto flex min-h-full w-full max-w-[768px] flex-col gap-3 bg-ink p-4 text-white sm:rounded-[28px]">
      <header className="flex min-h-touch items-center justify-between">
        <div className="flex flex-col"><span className="text-[17px] font-extrabold">Plaza Serrano</span><span className="text-xs text-ink-subtle">Operador · {user?.nombre ?? 'Playero'}</span></div>
        <span className="flex h-11 w-11 items-center justify-center rounded-full bg-ink-800 text-sm font-extrabold">{(user?.nombre ?? 'P').slice(0, 2).toUpperCase()}</span>
      </header>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="flex flex-col gap-3">
          <TrafficLight ocupacion={ocupacion} />
          <QrViewfinder active={!!mode && !busy} onScan={onScan} />
        </div>

        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-2.5">
            <button onClick={() => setMode('ingreso')} aria-pressed={mode === 'ingreso'}
              className={`flex min-h-[76px] flex-col items-center justify-center rounded-sheet text-[17px] font-extrabold transition ${mode === 'ingreso' ? 'bg-action text-ink' : 'bg-ink-800 text-white hover:bg-ink-700'}`}>
              Escanear<span className="text-xl">Ingreso</span>
            </button>
            <button onClick={() => setMode('egreso')} aria-pressed={mode === 'egreso'}
              className={`flex min-h-[76px] flex-col items-center justify-center rounded-sheet text-[17px] font-extrabold transition ${mode === 'egreso' ? 'bg-brand text-white' : 'bg-ink-800 text-white hover:bg-ink-700'}`}>
              Escanear<span className="text-xl">Egreso</span>
            </button>
          </div>
          <button onClick={() => setMode('sin_lugar')} aria-pressed={mode === 'sin_lugar'}
            className={`min-h-touch rounded-card border-[1.5px] px-4 text-sm font-bold transition ${mode === 'sin_lugar' ? 'border-debt bg-debt/15 text-debt-light' : 'border-ink-700 text-ink-subtle hover:text-white'}`}>
            Llegó con reserva y no hay lugar físico
          </button>
          {mode === 'sin_lugar' && <p className="text-xs text-ink-subtle">Escaneá su QR: se reembolsa la reserva y le ofrecés un garaje cercano.</p>}

          <form onSubmit={submitManual} className="flex gap-2">
            <input value={manual} onChange={(e) => setManual(e.target.value)} placeholder="Patente o código manual"
              className="min-h-[52px] flex-1 rounded-[14px] border-[1.5px] border-ink-700 bg-transparent px-4 font-mono text-base tracking-wider text-white placeholder:font-sans placeholder:tracking-normal placeholder:text-ink-subtle focus:border-brand focus:outline-none" />
            <button disabled={!mode || busy || !manual} className="btn-ghost-dark min-h-[52px]">{busy ? '…' : 'OK'}</button>
          </form>

          {mode === 'ingreso' && isPatenteValida(manual) && (
            <div className="flex flex-col gap-2 rounded-card border border-ink-700 p-3">
              <span className="text-sm font-bold">Cliente sin reserva · ¿cuánto se queda?</span>
              <div className="flex gap-2" role="radiogroup" aria-label="Salida estimada">
                {[...new Set([...SALIDAS, ocupacion?.ventana_min ?? 120])].sort((a, b) => a - b).map((m) => (
                  <button key={m} type="button" role="radio" aria-checked={ventana === m} onClick={() => setSalidaMin(m)}
                    className={`min-h-[44px] flex-1 rounded-[10px] text-sm font-bold ${ventana === m ? 'bg-brand text-white' : 'bg-ink-800 text-ink-subtle'}`}>{horasLabel(m)}</button>
                ))}
              </div>
              {sinLugarPresencial && <span className="text-xs font-bold text-debt-light">El semáforo está en rojo: este cliente no puede entrar sin chocar con reservas.</span>}
            </div>
          )}

          {derivar && (
            <div className="flex flex-col gap-2">
              {derivar.detalle && <p role="alert" className="rounded-card bg-debt/15 px-4 py-3 text-sm font-bold text-debt-light">{derivar.detalle}</p>}
              <CercanosList dark titulo={derivar.titulo} cercanos={derivar.cercanos} loading={!derivar.cercanos} />
              <button onClick={() => setDerivar(null)} className="self-end text-sm font-bold text-ink-subtle hover:text-white">Cerrar</button>
            </div>
          )}

          {feedback && (
            <div role="alert" className={`rounded-card px-4 py-3 text-sm font-bold ${feedback.ok ? 'bg-action/15 text-action' : 'bg-debt/15 text-debt-light'}`}>{feedback.text}</div>
          )}

          <div className="flex flex-col gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-ink-subtle">Últimos movimientos</span>
            {movs.length === 0 && <span className="text-sm text-ink-subtle">Todavía no hay movimientos en este turno.</span>}
            {movs.map((r) => (
              <div key={r.id} className={`flex min-h-touch items-center gap-2.5 rounded-card bg-ink-900 px-3 border-l-4 ${r.origen === 'APP' ? 'border-brand' : 'border-dashed border-[#7A8496]'}`}>
                <VehiclePlateBadge patente={r.patente} size="sm" dark className="border-0 px-0" />
                <span className={`text-[11px] font-bold ${r.origen === 'APP' ? 'text-[#7FB2FF]' : 'text-ink-subtle'}`}>{r.origen !== 'APP' ? 'Sin reserva' : r.modalidad && r.modalidad !== 'HORA' ? 'Abono' : 'App'}</span>
                <StatusBadge estado={r.estado} variant="dark" className="ml-auto" />
              </div>
            ))}
          </div>
        </div>
      </div>

      {deuda && <OverstayModal deuda={deuda} onClose={() => { setDeuda(null); setFeedback({ ok: true, text: 'Deuda saldada. Salida liberada.' }); loadOcupacion(); }} />}
    </div>
  );
}
