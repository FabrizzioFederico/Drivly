import { finDeAbono } from '../lib/format';

// Backend simulado en memoria. Se activa con VITE_USE_MOCKS=true.
// Respeta las mismas formas de respuesta que se esperan de DRF (snake_case).
// Reglas de la documentación que simula:
//   Regla 3  la categoría sale del vehículo validado, nunca del cliente.
//   Regla 5  abonos semanales, mensuales y anuales en cochera móvil, con cupo máximo.
//   Regla 6  app y presenciales comparten una única capacidad; si chocan, se derivan a garajes cercanos.

const wait = (ms = 350) => new Promise((r) => setTimeout(r, ms));
const uid = (p = 'DRV') => `${p}-` + Math.random().toString(36).slice(2, 6).toUpperCase() + '-' + Math.random().toString(36).slice(2, 6).toUpperCase();
const fail = (status, detail, extra = {}) => Promise.reject({ isDrivlyError: true, status, message: detail, fields: extra.fields ?? {}, code: extra.code, data: extra });
const firma = (id) => [...id].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7).toString(36);
const UNIDAD = { HORA: '/ 15 min', SEMANAL: '/ semana', MENSUAL: '/ mes', ANUAL: '/ año' };

const garajes = [
  { id: 1, nombre: 'Garage Plaza Serrano', direccion: 'Honduras 4870, Palermo', lat: -34.5889, lng: -58.4306, techado: true, abierto_24h: false,
    capacidad: 80, cupo_abonos: 10, tolerancia_min: 15, salida_estimada_default_min: 120, recargo_overstay: 0.5, libres: 10, abonos_activos: 8 },
  { id: 2, nombre: 'Estacionamiento Gurruchaga', direccion: 'Gurruchaga 1650, Palermo', lat: -34.5872, lng: -58.4291, techado: false, abierto_24h: true,
    capacidad: 50, cupo_abonos: 5, tolerancia_min: 10, salida_estimada_default_min: 120, recargo_overstay: 0.5, libres: 4, abonos_activos: 2 },
  { id: 3, nombre: 'Parking Armenia', direccion: 'Armenia 1420, Palermo', lat: -34.5901, lng: -58.4285, techado: true, abierto_24h: false,
    capacidad: 60, cupo_abonos: 0, tolerancia_min: 15, salida_estimada_default_min: 90, recargo_overstay: 0.5, libres: 0, abonos_activos: 0 },
  { id: 4, nombre: 'Cochera Thames', direccion: 'Thames 1580, Palermo', lat: -34.5878, lng: -58.4334, techado: true, abierto_24h: true,
    capacidad: 30, cupo_abonos: 6, tolerancia_min: 10, salida_estimada_default_min: 120, recargo_overstay: 0.5, libres: 12, abonos_activos: 1 },
];

// Tarifas con la misma forma que el backend: una fila por garaje, categoría y modalidad.
const hora = (categoria, precio, minimo = 1) => ({ categoria, modalidad: 'HORA', precio_fraccion: precio, fraccion_min: 15, minimo_fracciones: minimo, precio_periodo: null });
const abono = (categoria, modalidad, precio) => ({ categoria, modalidad, precio_fraccion: null, fraccion_min: null, minimo_fracciones: null, precio_periodo: precio });
const tarifas = {
  1: [hora('AUTO', 320, 4), hora('MOTO', 160, 2), hora('CAMIONETA', 450, 4),
      abono('AUTO', 'SEMANAL', 42000), abono('AUTO', 'MENSUAL', 150000), abono('AUTO', 'ANUAL', 1550000),
      abono('MOTO', 'MENSUAL', 70000), abono('CAMIONETA', 'MENSUAL', 210000)],
  2: [hora('AUTO', 280), hora('MOTO', 140), hora('CAMIONETA', 400), abono('AUTO', 'MENSUAL', 135000), abono('MOTO', 'MENSUAL', 60000)],
  3: [hora('AUTO', 300), hora('MOTO', 150), hora('CAMIONETA', 420)],
  4: [hora('AUTO', 340), hora('MOTO', 170), hora('CAMIONETA', 470), abono('AUTO', 'SEMANAL', 45000), abono('AUTO', 'MENSUAL', 160000), abono('AUTO', 'ANUAL', 1600000)],
};
const tarifaDe = (g, categoria, modalidad) => tarifas[g]?.find((t) => t.categoria === categoria && t.modalidad === modalidad);

let vehiculos = [
  { id: 'veh-1', patente: 'AA123BB', categoria: 'AUTO', estado_validacion: 'VALIDADO' },
  { id: 'veh-2', patente: 'A123BCD', categoria: 'MOTO', estado_validacion: 'VALIDADO' },
  { id: 'veh-3', patente: 'ERR123', categoria: null, estado_validacion: 'PENDIENTE' },
];

const hoyA = (h, m = 0) => { const d = new Date(); d.setHours(h, m, 0, 0); return d.toISOString(); };

let reservas = [
  { id: 'DRV-7F3K-92QA', patente: 'AA123BB', categoria: 'AUTO', origen: 'APP', modalidad: 'HORA', inicio: hoyA(14, 30), fin: hoyA(17, 30), estado: 'EN_CURSO', total: 4090, garaje: 1 },
  { id: 'DRV-2M8P-41XC', patente: 'AD772FG', categoria: 'AUTO', origen: 'APP', modalidad: 'HORA', inicio: hoyA(16), fin: hoyA(18), estado: 'CONFIRMADA', total: 2810, garaje: 1 },
  { id: 'DRV-9Q1L-07TB', patente: 'A123BCD', categoria: 'MOTO', origen: 'APP', modalidad: 'HORA', inicio: hoyA(16, 15), fin: hoyA(17), estado: 'HOLD', total: 480, garaje: 1 },
  { id: 'DRV-5H6N-33RA', patente: 'AB456CD', categoria: 'AUTO', origen: 'APP', modalidad: 'HORA', inicio: hoyA(15), fin: hoyA(17, 30), estado: 'CON_DEUDA', total: 960, garaje: 1 },
  { id: 'ABN-8K2W-58JD', patente: 'AE301HJ', categoria: 'CAMIONETA', origen: 'APP', modalidad: 'MENSUAL', inicio: hoyA(0), fin: finDeAbono(hoyA(0), 'MENSUAL').toISOString(), estado: 'CONFIRMADA', total: 210250, garaje: 1 },
  { id: 'PRS-0412', patente: 'AC908KL', categoria: 'AUTO', origen: 'PRESENCIAL', modalidad: 'PRESENCIAL', inicio: hoyA(13), fin: hoyA(16), estado: 'EN_CURSO', total: 3360, garaje: 1 },
];

// Ocupación del garaje 1 (el del playero y el admin de la demo)
let ocup = { ocupados_app: 30, ocupados_presencial: 32, ocupados_abonos: 8, proximas_app: 6, ventana_min: 120 };
let egresoCount = 0;
const deudaPolls = {};

const distancia = (a, b) => {
  const R = 6371000; const rad = (x) => (x * Math.PI) / 180;
  const h = Math.sin(rad(b.lat - a.lat) / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lng - a.lng) / 2) ** 2;
  return Math.round(2 * R * Math.asin(Math.sqrt(h)));
};

/** Lugares libres de un garaje para una modalidad (hora: rotación; abonos: cupo de abonos). */
function libresPara(g, modalidad) {
  if (modalidad === 'HORA' || !modalidad) return g.libres;
  if (!tarifas[g.id]?.some((t) => t.modalidad === modalidad)) return null; // no ofrece la modalidad
  return Math.max(0, Math.min(g.cupo_abonos - g.abonos_activos, g.libres));
}

function precioDesde(g, modalidad = 'HORA') {
  const filas = (tarifas[g.id] || []).filter((t) => t.modalidad === modalidad);
  if (!filas.length) return null;
  return Math.min(...filas.map((t) => t.precio_fraccion ?? t.precio_periodo));
}

function resumen(g, origen, modalidad) {
  return {
    id: g.id, nombre: g.nombre, direccion: g.direccion, lat: g.lat, lng: g.lng, techado: g.techado, abierto_24h: g.abierto_24h,
    distancia_m: distancia(origen, g), lugares_libres: libresPara(g, modalidad),
    precio_desde: precioDesde(g, modalidad), precio_unidad: UNIDAD[modalidad || 'HORA'],
  };
}

/** Garajes con lugar cerca de otro (o de un punto), ordenados por distancia. */
function cercanosA(origen, { excluir, modalidad = 'HORA', radio = 1000 } = {}) {
  return garajes
    .filter((g) => g.id !== excluir)
    .map((g) => resumen(g, origen, modalidad))
    .filter((g) => g.lugares_libres > 0 && g.distancia_m <= radio)
    .sort((a, b) => a.distancia_m - b.distancia_m);
}

function ocupacionDe(g) {
  const libres = Math.max(0, g.capacidad - ocup.ocupados_app - ocup.ocupados_presencial - ocup.ocupados_abonos);
  return {
    capacidad: g.capacidad, ...ocup, libres,
    // Lo que puede entrar sin reserva: libres menos los conductores de la app que llegan dentro de la ventana.
    libres_presencial: Math.max(0, libres - ocup.proximas_app),
  };
}

export const mocks = {
  async loginWithGoogle() {
    await wait();
    return { access: 'mock-access', refresh: 'mock-refresh', user: { id: 1, nombre: 'Laura Gómez', email: 'laura@drivly.app', rol: 'ADMIN', garaje: 1 } };
  },
  async me() { await wait(150); return { id: 1, nombre: 'Laura Gómez', rol: 'ADMIN', garaje: 1 }; },

  /* ---------- Vehículos (regla 3) ---------- */
  async listVehiculos() { await wait(); return vehiculos; },
  async createVehiculo({ patente }) {
    await wait(700);
    const p = patente.replace(/[\s-]/g, '').toUpperCase();
    if (vehiculos.some((v) => v.patente === p)) return fail(400, 'Esta patente ya está registrada en Drivly.', { fields: { patente: ['Esta patente ya está registrada en Drivly.'] } });
    // Mismas reglas que MockPatenteGateway del backend
    let v = { id: uid('veh'), patente: p, categoria: null, estado_validacion: 'PENDIENTE' };
    if (p.startsWith('ERR')) v.estado_validacion = 'PENDIENTE';
    else if (p.endsWith('ZZ')) v.estado_validacion = 'RECHAZADO';
    else if (/^(\d{3}[A-Z]{3}|[A-Z]\d{3}[A-Z]{3})$/.test(p)) v = { ...v, categoria: 'MOTO', estado_validacion: 'VALIDADO' };
    else v = { ...v, categoria: p.startsWith('AE') ? 'CAMIONETA' : 'AUTO', estado_validacion: 'VALIDADO' };
    vehiculos = [...vehiculos, v];
    return v;
  },
  async revalidarVehiculo(id) { await wait(700); return vehiculos.find((v) => v.id === id); },

  /* ---------- Garajes ---------- */
  async listGarajes() { await wait(); return garajes; },
  async getGaraje(id) { await wait(); return garajes.find((g) => g.id === Number(id)); },
  async garajesDisponibles({ lat, lng, modalidad = 'HORA' } = {}) {
    await wait(500);
    return garajes.map((g) => resumen(g, { lat, lng }, modalidad)).filter((g) => g.lugares_libres !== null).sort((a, b) => a.distancia_m - b.distancia_m);
  },
  async cercanos(id, { modalidad = 'HORA' } = {}) {
    await wait(400);
    const g = garajes.find((x) => x.id === Number(id));
    return cercanosA(g, { excluir: g.id, modalidad });
  },
  async getTarifas(id) { await wait(); return tarifas[Number(id)] ?? []; },
  async updateTarifas(id, filas) { await wait(); tarifas[Number(id)] = filas; return filas; },
  async updateConfiguracion(id, body) {
    await wait();
    const g = garajes.find((x) => x.id === Number(id));
    if (body.cupo_abonos > body.capacidad) return fail(400, 'El cupo de abonos no puede superar la capacidad.', { fields: { cupo_abonos: ['No puede superar la capacidad.'] } });
    Object.assign(g, body);
    return g;
  },

  async ocupacion(id) {
    await wait(200);
    const g = garajes.find((x) => x.id === Number(id)) || garajes[0];
    const app = [4, 6, 12, 20, 26, 28, 30, 32, 34, 36, 38, 40, 38, 30, 22, 14, 8, 4];
    const walk = [6, 10, 18, 24, 28, 30, 30, 32, 34, 32, 34, 32, 30, 26, 20, 14, 8, 4];
    const nowH = new Date().getHours();
    return {
      ...ocupacionDe(g), umbral_alerta: 0.9,
      franjas: app.map((a, i) => ({ hora: 6 + i, app: a + ocup.ocupados_abonos, presencial: walk[i], proyectada: 6 + i > nowH })),
    };
  },

  async metricas() {
    await wait();
    return { ocupacion_pico: 0.9, ocupacion_pico_hora: '17:00', ocupacion_pico_lugares: 72, reservas_confirmadas: 58, reservas_variacion: 12, en_hold: 3, canceladas: 2, recaudacion_total: 412380, recaudacion_app: 268900, recaudacion_presencial: 131200, recaudacion_excedentes: 12280 };
  },

  /* ---------- Reservas ---------- */
  async listReservas({ estado } = {}) {
    await wait();
    return estado ? reservas.filter((r) => r.estado === estado) : reservas;
  },
  async getReserva(id) { await wait(); return reservas.find((r) => r.id === id); },

  async createHold({ garaje, vehiculo, modalidad = 'HORA', inicio, fin }) {
    await wait(600);
    const g = garajes.find((x) => x.id === Number(garaje));
    const v = vehiculos.find((x) => x.id === vehiculo);
    if (!v) return fail(400, 'Elegí uno de tus vehículos.');
    if (v.estado_validacion !== 'VALIDADO') return fail(422, 'Tu vehículo todavía no está validado con el registro oficial.');
    const t = tarifaDe(g.id, v.categoria, modalidad);
    if (!t) return fail(409, `Este garaje no ofrece ${modalidad === 'HORA' ? 'reservas por hora' : `abono ${modalidad.toLowerCase()}`} para ${v.categoria.toLowerCase()}.`);
    if (!(libresPara(g, modalidad) > 0)) {
      return fail(409, 'No queda lugar en este garaje para ese horario.', { code: 'SIN_CUPO', cercanos: cercanosA(g, { excluir: g.id, modalidad }) });
    }
    const cargo_servicio = 250;
    let desglose;
    let finReal = fin;
    if (modalidad === 'HORA') {
      const minutos = Math.ceil((new Date(fin) - new Date(inicio)) / 60000);
      const fracciones = Math.max(t.minimo_fracciones, Math.ceil(minutos / t.fraccion_min));
      desglose = { modalidad, precio_fraccion: t.precio_fraccion, fraccion_min: t.fraccion_min, fracciones, minimo_fracciones: t.minimo_fracciones, minimo_aplicado: fracciones === t.minimo_fracciones && minutos < t.minimo_fracciones * t.fraccion_min, subtotal: fracciones * t.precio_fraccion, cargo_servicio };
    } else {
      finReal = finDeAbono(inicio, modalidad).toISOString();
      desglose = { modalidad, precio_periodo: t.precio_periodo, subtotal: t.precio_periodo, cargo_servicio };
    }
    const r = {
      id: uid(modalidad === 'HORA' ? 'DRV' : 'ABN'), garaje: g.id, garaje_detalle: g, vehiculo: v.id, patente: v.patente, categoria: v.categoria,
      origen: 'APP', modalidad, inicio, fin: finReal, estado: 'HOLD', hold_expira_en: new Date(Date.now() + 5 * 60000).toISOString(),
      desglose, total: desglose.subtotal + cargo_servicio,
    };
    reservas = [r, ...reservas];
    return r;
  },

  async pagar(id) {
    await wait(900);
    const r = reservas.find((x) => x.id === id);
    if (!r || r.estado !== 'HOLD') return fail(409, 'La reserva ya no está retenida. Volvé a reservar.');
    if (new Date(r.hold_expira_en) < new Date()) { r.estado = 'EXPIRADA'; return fail(410, 'Pasaron los 5 minutos y el lugar se liberó.'); }
    r.estado = 'CONFIRMADA';
    return r;
  },

  async cancelar(id) {
    await wait();
    const r = reservas.find((x) => x.id === id);
    if (r) r.estado = r.estado === 'HOLD' ? 'EXPIRADA' : 'CANCELADA';
    return r;
  },

  /** QR estático y firmado: no vence mientras la reserva esté vigente, por eso funciona sin conexión. */
  async getQr(id) {
    await wait(150);
    const r = reservas.find((x) => x.id === id);
    return { qr_token: `drivly.v1.${id}.${firma(id)}`, valido_desde: r?.inicio, valido_hasta: r?.fin, reutilizable: r ? r.modalidad !== 'HORA' : false };
  },

  /* ---------- Operación del playero ---------- */
  async ingreso({ qr_token, patente, salida_estimada }) {
    await wait(500);
    const g = garajes[0];
    if (qr_token) {
      const [pre, ver, id, sig] = qr_token.split('.');
      if (pre !== 'drivly' || ver !== 'v1' || sig !== firma(id ?? '')) return fail(400, 'QR inválido: la firma no coincide.');
      const r = reservas.find((x) => x.id === id);
      if (!r) return fail(404, 'No existe una reserva con ese QR.');
      const vigente = r.estado === 'CONFIRMADA' || (r.modalidad !== 'HORA' && r.modalidad !== 'PRESENCIAL' && r.estado === 'EN_CURSO');
      if (!vigente) return fail(409, `La reserva está ${r.estado.replace('_', ' ').toLowerCase()} y no habilita el ingreso.`);
      r.estado = 'EN_CURSO';
      if (r.modalidad === 'HORA') { ocup.ocupados_app++; ocup.proximas_app = Math.max(0, ocup.proximas_app - 1); }
      return { reserva: r, ocupacion: await mocks.ocupacion(g.id) };
    }
    // Cliente presencial: sólo entra si hay lugar sin chocar con las reservas que están por llegar (regla 6)
    if (ocupacionDe(g).libres_presencial <= 0) {
      return fail(409, 'No hay lugar para clientes sin reserva: los libres están comprometidos con reservas de la app.', { code: 'SIN_LUGAR_PRESENCIAL', cercanos: cercanosA(g, { excluir: g.id }) });
    }
    const r = { id: 'PRS-' + Math.floor(Math.random() * 9000 + 1000), patente, categoria: 'AUTO', origen: 'PRESENCIAL', modalidad: 'PRESENCIAL', inicio: new Date().toISOString(), fin: salida_estimada, estado: 'EN_CURSO', total: 0, garaje: g.id };
    reservas = [r, ...reservas];
    ocup.ocupados_presencial++;
    return { reserva: r, ocupacion: await mocks.ocupacion(g.id) };
  },

  async egreso({ qr_token, patente }) {
    await wait(500);
    egresoCount++;
    const id = qr_token ? qr_token.split('.')[2] : null;
    const r = reservas.find((x) => x.id === id || x.patente === patente) || reservas[3];
    const g = garajes.find((x) => x.id === r.garaje) || garajes[0];
    // Cada 2° egreso simulado genera deuda por overstay para poder probar el modal
    if (egresoCount % 2 === 0 || r.estado === 'CON_DEUDA') {
      r.estado = 'CON_DEUDA';
      const t = tarifaDe(g.id, r.categoria, 'HORA') || tarifas[1][0];
      const minutos = 30;
      const fracciones = Math.ceil(minutos / t.fraccion_min);
      const total = Math.round(fracciones * t.precio_fraccion * (1 + g.recargo_overstay));
      return {
        reserva: r,
        deuda: { reserva_id: r.id, patente: r.patente, minutos_excedidos: minutos, tolerancia_min: g.tolerancia_min, fraccion_min: t.fraccion_min, fracciones, precio_fraccion: t.precio_fraccion, recargo: g.recargo_overstay, total, fin_reservado: hoyA(17, 30), egreso_real: hoyA(18, 15), mp_qr_data: `00020101021243650016COM.MERCADOLIBRE0201306364${r.id}5204597053030325802AR5909DRIVLY6304` },
      };
    }
    r.estado = r.modalidad === 'HORA' || r.modalidad === 'PRESENCIAL' ? 'FINALIZADA' : r.estado;
    if (r.origen === 'PRESENCIAL') ocup.ocupados_presencial = Math.max(0, ocup.ocupados_presencial - 1);
    else ocup.ocupados_app = Math.max(0, ocup.ocupados_app - 1);
    return { reserva: r, deuda: null };
  },

  /** Conductor con reserva que llega y no hay lugar físico: reembolso + garajes cercanos (regla 6). */
  async sinLugar({ qr_token }) {
    await wait(600);
    const [, , id, sig] = (qr_token || '').split('.');
    if (sig !== firma(id ?? '')) return fail(400, 'QR inválido: la firma no coincide.');
    const r = reservas.find((x) => x.id === id);
    if (!r || r.estado !== 'CONFIRMADA') return fail(409, 'Sólo se puede marcar sin lugar una reserva confirmada que todavía no ingresó.');
    r.estado = 'SIN_LUGAR';
    const g = garajes.find((x) => x.id === r.garaje) || garajes[0];
    return { reserva: r, reembolso: { monto: r.total, estado: 'SOLICITADO' }, cercanos: cercanosA(g, { excluir: g.id, modalidad: r.modalidad === 'PRESENCIAL' ? 'HORA' : r.modalidad }) };
  },

  async estadoDeuda(id) {
    await wait(300);
    deudaPolls[id] = (deudaPolls[id] || 0) + 1;
    const pagado = deudaPolls[id] >= 4;
    if (pagado) { const r = reservas.find((x) => x.id === id); if (r) r.estado = 'FINALIZADA'; }
    return { pagado, transaccion_id: pagado ? 'MP-' + Math.floor(Math.random() * 1e8) : null };
  },

  async registrarEfectivo(id) {
    await wait();
    const r = reservas.find((x) => x.id === id);
    if (r) r.estado = 'FINALIZADA';
    return { pagado: true, medio: 'EFECTIVO' };
  },
};
