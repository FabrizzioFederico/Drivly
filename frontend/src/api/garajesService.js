import client, { USE_MOCKS } from './client';
import { mocks } from './mocks';

const lista = (data) => (Array.isArray(data) ? data : data.results);

export const garajesService = {
  /** GET /garajes/ (garajes del admin autenticado) */
  async list(params = {}) {
    if (USE_MOCKS) return mocks.listGarajes();
    return lista((await client.get('/garajes/', { params })).data);
  },

  /** GET /garajes/{id}/ */
  async get(id) {
    if (USE_MOCKS) return mocks.getGaraje(id);
    return (await client.get(`/garajes/${id}/`)).data;
  },

  /**
   * GET /garajes/disponibles/?lat=&lng=&radio=&inicio=&fin=&modalidad=HORA|SEMANAL|MENSUAL|ANUAL
   * -> [{ id, nombre, direccion, lat, lng, distancia_m, lugares_libres, precio_desde, precio_unidad, techado, abierto_24h }]
   * Sólo devuelve garajes que ofrecen la modalidad pedida.
   */
  async disponibles(params) {
    if (USE_MOCKS) return mocks.garajesDisponibles(params);
    return lista((await client.get('/garajes/disponibles/', { params })).data);
  },

  /**
   * GET /garajes/{id}/cercanos/?inicio=&fin=&modalidad=  (regla 6)
   * Garajes con lugar cerca de uno que está lleno, ordenados por distancia. Misma forma que disponibles().
   */
  async cercanos(id, params = {}) {
    if (USE_MOCKS) return mocks.cercanos(id, params);
    return lista((await client.get(`/garajes/${id}/cercanos/`, { params })).data);
  },

  /**
   * GET /garajes/{id}/tarifas/
   * -> [{ categoria, modalidad, precio_fraccion, fraccion_min, minimo_fracciones, precio_periodo }]
   * HORA usa fracciones; SEMANAL / MENSUAL / ANUAL usan precio_periodo.
   */
  async getTarifas(id) {
    if (USE_MOCKS) return mocks.getTarifas(id);
    return (await client.get(`/garajes/${id}/tarifas/`)).data;
  },

  /** PUT /garajes/{id}/tarifas/ con la lista completa: las modalidades que no vienen dejan de ofrecerse (CU-06) */
  async updateTarifas(id, filas) {
    if (USE_MOCKS) return mocks.updateTarifas(id, filas);
    return (await client.put(`/garajes/${id}/tarifas/`, filas)).data;
  },

  /**
   * PATCH /garajes/{id}/ (CU-06)
   * { capacidad, cupo_abonos, salida_estimada_default_min, tolerancia_min, recargo_overstay }
   * Una sola capacidad compartida por app y presenciales; cupo_abonos es un máximo dentro de ella.
   */
  async updateConfiguracion(id, body) {
    if (USE_MOCKS) return mocks.updateConfiguracion(id, body);
    return (await client.patch(`/garajes/${id}/`, body)).data;
  },

  /**
   * GET /garajes/{id}/ocupacion/
   * -> { capacidad, ocupados_app, ocupados_presencial, ocupados_abonos, proximas_app, ventana_min,
   *      libres, libres_presencial, umbral_alerta, franjas: [{ hora, app, presencial, proyectada }] }
   * libres_presencial = libres - reservas de la app que llegan dentro de la ventana (semáforo, regla 6).
   */
  async ocupacion(id) {
    if (USE_MOCKS) return mocks.ocupacion(id);
    return (await client.get(`/garajes/${id}/ocupacion/`)).data;
  },

  /** GET /garajes/{id}/metricas/?fecha=YYYY-MM-DD (CU-10) */
  async metricas(id, params = {}) {
    if (USE_MOCKS) return mocks.metricas(id);
    return (await client.get(`/garajes/${id}/metricas/`, { params })).data;
  },
};
