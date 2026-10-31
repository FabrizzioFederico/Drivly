// Backend simulado en memoria. Se activa con VITE_USE_MOCKS=true.
// Respeta las mismas formas de respuesta que se esperan de DRF (snake_case).
// Sólo lo que usa el portal del administrador.

const wait = (ms = 350) => new Promise((r) => setTimeout(r, ms));
const fail = (status, detail, extra = {}) => Promise.reject({ isDrivlyError: true, status, message: detail, fields: extra.fields ?? {}, code: extra.code, data: extra });
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
const hoyA = (h, m = 0) => { const d = new Date(); d.setHours(h, m, 0, 0); return d.toISOString(); };

let reservas = [
  { id: 'DRV-7F3K-92QA', patente: 'AA123BB', categoria: 'AUTO', origen: 'APP', modalidad: 'HORA', inicio: hoyA(14, 30), fin: hoyA(17, 30), estado: 'EN_CURSO', total: 4090, garaje: 1 },
  { id: 'DRV-2M8P-41XC', patente: 'AD772FG', categoria: 'AUTO', origen: 'APP', modalidad: 'HORA', inicio: hoyA(16), fin: hoyA(18), estado: 'CONFIRMADA', total: 2810, garaje: 1 },
  { id: 'DRV-9Q1L-07TB', patente: 'A123BCD', categoria: 'MOTO', origen: 'APP', modalidad: 'HORA', inicio: hoyA(16, 15), fin: hoyA(17), estado: 'HOLD', total: 480, garaje: 1 },
  { id: 'DRV-5H6N-33RA', patente: 'AB456CD', categoria: 'AUTO', origen: 'APP', modalidad: 'HORA', inicio: hoyA(15), fin: hoyA(17, 30), estado: 'CON_DEUDA', total: 960, garaje: 1 },
  { id: 'ABN-8K2W-58JD', patente: 'AE301HJ', categoria: 'CAMIONETA', origen: 'APP', modalidad: 'MENSUAL', inicio: hoyA(0), fin: new Date(Date.now() + 30 * 864e5).toISOString(), estado: 'CONFIRMADA', total: 210250, garaje: 1 },
  { id: 'PRS-0412', patente: 'AC908KL', categoria: 'AUTO', origen: 'PRESENCIAL', modalidad: 'PRESENCIAL', inicio: hoyA(13), fin: hoyA(16), estado: 'EN_CURSO', total: 3360, garaje: 1 },
];

// Ocupación del garaje 1 (el del playero y el admin de la demo)
let ocup = { ocupados_app: 30, ocupados_presencial: 32, ocupados_abonos: 8, proximas_app: 6, ventana_min: 120 };
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
    return { access: 'mock-access', refresh: 'mock-refresh', user: { id: 1, nombre: 'Laura Gómez', email: 'laura@drivly.app', rol: 'ADMIN_GARAJE', garaje: 1 } };
  },
  async me() { await wait(150); return { id: 1, nombre: 'Laura Gómez', rol: 'ADMIN_GARAJE', garaje: 1 }; },

  /* ---------- Garajes ---------- */
  async listGarajes() { await wait(); return garajes; },
  async getGaraje(id) { await wait(); return garajes.find((g) => g.id === Number(id)); },
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

  /* ---------- Reservas y deudas ---------- */
  async listReservas({ estado } = {}) {
    await wait();
    return estado ? reservas.filter((r) => r.estado === estado) : reservas;
  },
  async deudas() {
    await wait();
    return [];
  },

  async condonar(id) {
    await wait();
    return { reserva_id: id, estado: 'CONDONADA' };
  },
};
