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

  /** PUT /garajes/{id}/foto/ (multipart): foto del frente, la ve el conductor en la app. Devuelve el garaje. */
  async subirFoto(id, archivo) {
    const datos = new FormData();
    datos.append('foto', archivo);
    // multipart: el navegador completa el boundary (si quedara JSON, axios convertiría el FormData)
    return (await client.put(`/garajes/${id}/foto/`, datos, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000 })).data;
  },

  /** DELETE /garajes/{id}/foto/ */
  async quitarFoto(id) {
    return (await client.delete(`/garajes/${id}/foto/`)).data;
  },

  /** GET /garajes/{id}/informe/?desde&hasta (AAAA-MM-DD): ingresos por medio, comisión y cierres de caja */
  async informe(id, params) {
    return (await client.get(`/garajes/${id}/informe/`, { params })).data;
  },

  /** GET /garajes/{id}/informe/pdf/?desde&hasta: el mismo informe en PDF (se baja como archivo) */
  async informePdf(id, params) {
    const r = await client.get(`/garajes/${id}/informe/pdf/`, { params, responseType: 'blob' });
    const nombre = /filename="([^"]+)"/.exec(r.headers['content-disposition'] ?? '')?.[1] ?? 'drivly-informe.pdf';
    const url = URL.createObjectURL(r.data);
    Object.assign(document.createElement('a'), { href: url, download: nombre }).click();
    URL.revokeObjectURL(url);
  },

  /** GET /garajes/{id}/metricas/?fecha=YYYY-MM-DD (CU-10) */
  async metricas(id, params = {}) {
    if (USE_MOCKS) return mocks.metricas(id);
    return (await client.get(`/garajes/${id}/metricas/`, { params })).data;
  },

  /** GET /garajes/{id}/playeros/ -> [{ id, email, nombre, is_active }] */
  async getPlayeros(id) {
    if (USE_MOCKS) return [];
    return lista((await client.get(`/garajes/${id}/playeros/`)).data);
  },

  /** POST /garajes/{id}/playeros/ { email, nombre } */
  async addPlayero(id, body) {
    if (USE_MOCKS) return body;
    return (await client.post(`/garajes/${id}/playeros/`, body)).data;
  },

  /** DELETE /garajes/{id}/playeros/{usuarioId}/ */
  async removePlayero(garajeId, usuarioId) {
    if (USE_MOCKS) return;
    await client.delete(`/garajes/${garajeId}/playeros/${usuarioId}/`);
  },
};
