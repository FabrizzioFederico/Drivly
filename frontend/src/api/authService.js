import client, { tokenStore, USE_MOCKS } from './client';
import { mocks } from './mocks';

const USER_KEY = 'drivly.user';

export const authService = {
  /** POST /auth/google/ { id_token } -> { access, refresh, user } */
  async loginWithGoogle(idToken) {
    const data = USE_MOCKS
      ? await mocks.loginWithGoogle(idToken)
      : (await client.post('/auth/google/', { id_token: idToken })).data;
    tokenStore.set(data.access, data.refresh);
    if (data.user) localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    return data.user;
  },

  /** POST /auth/refresh/ { refresh } -> { access } (lo usa también el interceptor) */
  async refresh() {
    if (USE_MOCKS) return tokenStore.access;
    const { data } = await client.post('/auth/refresh/', { refresh: tokenStore.refresh });
    tokenStore.set(data.access, data.refresh);
    return data.access;
  },

  /** GET /auth/me/ -> perfil con rol: CONDUCTOR | PLAYERO | ADMIN */
  async me() {
    if (USE_MOCKS) return mocks.me();
    const { data } = await client.get('/auth/me/');
    localStorage.setItem(USER_KEY, JSON.stringify(data));
    return data;
  },

  cachedUser() {
    try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; }
  },

  isAuthenticated() { return Boolean(tokenStore.access); },

  logout() {
    tokenStore.clear();
    localStorage.removeItem(USER_KEY);
    window.dispatchEvent(new CustomEvent('drivly:logout'));
  },
};
