import client, { USE_MOCKS } from './client';
import { mocks } from './mocks';

export const operacionService = {
  /**
   * POST /operacion/ingreso/ (CU-07)
   * body: { garaje, qr_token }                              conductor con reserva
   *     | { garaje, patente, salida_estimada }              cliente presencial (regla 6)
   * -> { reserva, ocupacion }
   * 409 { code: 'SIN_LUGAR_PRESENCIAL', cercanos: [...] } si el presencial chocaría con reservas de la app.
   * 402 { code: 'DEUDA_PATENTE', deuda: {..., efectivo} } si la patente tiene una deuda de más de 72 h (CP-30).
   */
  async ingreso(payload) {
    if (USE_MOCKS) return mocks.ingreso(payload);
    return (await client.post('/operacion/ingreso/', payload)).data;
  },

  /**
   * POST /operacion/egreso/ (CU-08)
   * -> { reserva, deuda: null | { reserva_id, minutos_excedidos, tolerancia_min, fraccion_min, fracciones,
   *      precio_fraccion, recargo, total, mp_qr_data, fin_reservado, egreso_real } }
   * recargo es un porcentaje: 0.5 = +50 %.
   */
  async egreso(payload) {
    if (USE_MOCKS) return mocks.egreso(payload);
    return (await client.post('/operacion/egreso/', payload)).data;
  },

  /**
   * POST /operacion/sin-lugar/ { garaje, qr_token }  (regla 6)
   * Conductor con reserva que llega y no hay lugar físico.
   * -> { reserva (SIN_LUGAR), reembolso: { monto, estado }, cercanos: [...] }
   */
  async sinLugar(payload) {
    if (USE_MOCKS) return mocks.sinLugar(payload);
    return (await client.post('/operacion/sin-lugar/', payload)).data;
  },

  /** GET /operacion/deudas/{reservaId}/ -> { pagado, transaccion_id? } (polling del QR de Mercado Pago) */
  async estadoDeuda(reservaId) {
    if (USE_MOCKS) return mocks.estadoDeuda(reservaId);
    return (await client.get(`/operacion/deudas/${reservaId}/`)).data;
  },

  /** POST /operacion/deudas/{reservaId}/efectivo/ */
  async registrarEfectivo(reservaId) {
    if (USE_MOCKS) return mocks.registrarEfectivo(reservaId);
    return (await client.post(`/operacion/deudas/${reservaId}/efectivo/`)).data;
  },

  /** GET /operacion/deudas/?garaje= -> deudas impagas del garaje (sólo admin) */
  async deudas(garajeId) {
    if (USE_MOCKS) return mocks.deudas(garajeId);
    return (await client.get('/operacion/deudas/', { params: { garaje: garajeId } })).data;
  },

  /** POST /operacion/deudas/{reservaId}/condonar/ { motivo, monto? }: sin monto condona todo el saldo (regla 4). */
  async condonar(reservaId, payload) {
    if (USE_MOCKS) return mocks.condonar(reservaId, payload);
    return (await client.post(`/operacion/deudas/${reservaId}/condonar/`, payload)).data;
  },
};
