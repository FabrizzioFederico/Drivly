import client, { USE_MOCKS } from './client';
import { mocks } from './mocks';

export const reservasService = {
  /** GET /reservas/?garaje=1 -> lista (paginada o no) */
  async list(params = {}) {
    if (USE_MOCKS) return mocks.listReservas(params);
    const { data } = await client.get('/reservas/', { params });
    return Array.isArray(data) ? data : data.results;
  },
};
