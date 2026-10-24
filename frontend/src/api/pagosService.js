import client, { USE_MOCKS } from './client';

export const pagosService = {
  /** GET /pagos/oauth/estado/?garaje= -> { conectado, requiere_reautorizar, conectada_en } */
  async estadoMercadoPago(garajeId) {
    if (USE_MOCKS) return { conectado: false, requiere_reautorizar: false, conectada_en: null };
    return (await client.get('/pagos/oauth/estado/', { params: { garaje: garajeId } })).data;
  },

  /**
   * POST /pagos/oauth/conectar/ { garaje } -> { url }
   * La URL lleva a Mercado Pago para autorizar a Drivly; al volver, el backend redirige a /?mp_conexion=ok|error.
   */
  async conectarMercadoPago(garajeId) {
    return (await client.post('/pagos/oauth/conectar/', { garaje: garajeId })).data;
  },
};
