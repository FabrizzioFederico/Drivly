import client, { tokenStore, USE_MOCKS } from './client';
import { mocks } from './mocks';

const USER_KEY = 'drivly.user';
const ROL_DEL_PORTAL = 'ADMIN_GARAJE'; // conductores y playeros usan la app

export const authService = {
  /**
   * POST /auth/google/ { id_token, rol } -> { access, refresh, user }
   * El rol sólo se usa si la cuenta es nueva: quien se registra acá es administrador.
   */
  async loginWithGoogle(idToken) {
    let data;
    if (USE_MOCKS) {
      data = await mocks.loginWithGoogle(idToken);
    } else if (idToken === 'demo') {
      // Dev mode sin Google OAuth: usa el endpoint de desarrollo (solo DEBUG=True)
      data = (await client.post('/auth/dev-login/', { rol: ROL_DEL_PORTAL })).data;
    } else {
      data = (await client.post('/auth/google/', { id_token: idToken, rol: ROL_DEL_PORTAL })).data;
    }
    if (data.user?.rol !== ROL_DEL_PORTAL) {
      throw new Error('Este portal es sólo para administradores de garajes. Conductores y playeros usan la app de Drivly.');
    }
    tokenStore.set(data.access, data.refresh);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    return data.user;
  },

  /** POST /auth/refresh/ { refresh } -> { access } (lo usa también el interceptor) */
  async refresh() {
    if (USE_MOCKS) return tokenStore.access;
    const { data } = await client.post('/auth/refresh/', { refresh: tokenStore.refresh });
    tokenStore.set(data.access, data.refresh);
    return data.access;
  },

  /** GET /auth/me/ -> perfil con rol */
  async me() {
    if (USE_MOCKS) return mocks.me();
    const { data } = await client.get('/auth/me/');
    localStorage.setItem(USER_KEY, JSON.stringify(data));
    return data;
  },

  cachedUser() {
    try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; }
  },

  /** El admin que ya había iniciado sesión. Cierra las sesiones de conductor o playero anteriores a este portal. */
  sesionGuardada() {
    const user = this.cachedUser();
    if (tokenStore.access && user?.rol === ROL_DEL_PORTAL) return user;
    tokenStore.clear();
    localStorage.removeItem(USER_KEY);
    return null;
  },

  isAuthenticated() { return Boolean(tokenStore.access); },

  logout() {
    tokenStore.clear();
    localStorage.removeItem(USER_KEY);
    window.dispatchEvent(new CustomEvent('drivly:logout'));
  },
};
