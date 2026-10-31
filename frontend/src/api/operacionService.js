import client, { USE_MOCKS } from './client';
import { mocks } from './mocks';

export const operacionService = {
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
