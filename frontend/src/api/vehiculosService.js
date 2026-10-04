import client, { USE_MOCKS } from './client';
import { mocks } from './mocks';

/**
 * Vehículos del conductor (regla 3). La categoría la asigna el backend con patente.ar:
 * el cliente nunca la envía ni la elige.
 */
export const vehiculosService = {
  /** GET /vehiculos/ -> [{ id, patente, categoria, estado_validacion, validado_en }] */
  async list() {
    if (USE_MOCKS) return mocks.listVehiculos();
    const { data } = await client.get('/vehiculos/');
    return Array.isArray(data) ? data : data.results;
  },

  /** POST /vehiculos/ { patente } -> vehículo con estado VALIDADO, PENDIENTE o RECHAZADO */
  async create(patente) {
    if (USE_MOCKS) return mocks.createVehiculo({ patente });
    return (await client.post('/vehiculos/', { patente })).data;
  },

  /** POST /vehiculos/{id}/revalidar/ -> reintento si patente.ar no respondió */
  async revalidar(id) {
    if (USE_MOCKS) return mocks.revalidarVehiculo(id);
    return (await client.post(`/vehiculos/${id}/revalidar/`)).data;
  },
};
