import client, { USE_MOCKS } from './client';
import { mocks } from './mocks';

export const reservasService = {
  /** GET /reservas/?estado=HOLD&garaje=1 -> lista (paginada o no) */
  async list(params = {}) {
    if (USE_MOCKS) return mocks.listReservas(params);
    const { data } = await client.get('/reservas/', { params });
    return Array.isArray(data) ? data : data.results;
  },

  /** GET /reservas/{id}/ */
  async get(id) {
    if (USE_MOCKS) return mocks.getReserva(id);
    return (await client.get(`/reservas/${id}/`)).data;
  },

  /**
   * POST /reservas/hold/  (CU-04)
   * body: { garaje, vehiculo, modalidad, inicio, fin }
   *   - vehiculo: id de un vehículo VALIDADO del conductor. La categoría (y la tarifa) salen de ahí,
   *     el cliente no la envía (regla 3).
   *   - modalidad: HORA | SEMANAL | MENSUAL | ANUAL. En abonos el backend calcula el fin.
   * -> { id, estado: 'HOLD', hold_expira_en, desglose, total, ... }
   * 409 { code: 'SIN_CUPO', cercanos: [...] } si no hay lugar (regla 6).
   */
  async createHold(payload) {
    if (USE_MOCKS) return mocks.createHold(payload);
    return (await client.post('/reservas/hold/', payload)).data;
  },

  /** POST /reservas/{id}/cancelar/ -> libera el Hold o cancela una CONFIRMADA */
  async cancelar(id) {
    if (USE_MOCKS) return mocks.cancelar(id);
    return (await client.post(`/reservas/${id}/cancelar/`)).data;
  },

  /** POST /reservas/{id}/pagar/ -> { estado: 'CONFIRMADA', init_point? } */
  async pagar(id) {
    if (USE_MOCKS) return mocks.pagar(id);
    return (await client.post(`/reservas/${id}/pagar/`)).data;
  },

  /**
   * GET /reservas/{id}/qr/ -> { qr_token, valido_desde, valido_hasta, reutilizable }
   * Token estático firmado por el servidor (HMAC): no vence mientras la reserva esté vigente,
   * así que se guarda y funciona sin conexión (RFM-09). En abonos sirve para cada ingreso y egreso.
   */
  async getQr(id) {
    if (USE_MOCKS) return mocks.getQr(id);
    return (await client.get(`/reservas/${id}/qr/`)).data;
  },
};
