import axios from 'axios';

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
export const USE_MOCKS = String(import.meta.env.VITE_USE_MOCKS) === 'true';

const ACCESS_KEY = 'drivly.access';
const REFRESH_KEY = 'drivly.refresh';

export const tokenStore = {
  get access() { return localStorage.getItem(ACCESS_KEY); },
  get refresh() { return localStorage.getItem(REFRESH_KEY); },
  set(access, refresh) {
    if (access) localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

const client = axios.create({
  baseURL: API_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
});

client.interceptors.request.use((config) => {
  const token = tokenStore.access;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Una sola renovación en vuelo: las requests que fallen con 401 en paralelo esperan la misma promesa.
let refreshPromise = null;

function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = axios
      .post(`${API_URL}/auth/refresh/`, { refresh: tokenStore.refresh })
      .then(({ data }) => {
        // SimpleJWT devuelve { access } y, con ROTATE_REFRESH_TOKENS, también { refresh }
        tokenStore.set(data.access, data.refresh);
        return data.access;
      })
      .finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config || {};
    const isAuthCall = original.url?.includes('/auth/');

    if (error.response?.status === 401 && !original._retry && !isAuthCall && tokenStore.refresh) {
      original._retry = true;
      try {
        const access = await refreshAccessToken();
        original.headers.Authorization = `Bearer ${access}`;
        return client(original);
      } catch (refreshError) {
        tokenStore.clear();
        window.dispatchEvent(new CustomEvent('drivly:logout'));
        return Promise.reject(normalizeError(refreshError));
      }
    }
    return Promise.reject(normalizeError(error));
  }
);

/**
 * Normaliza errores de DRF:
 *  { detail: "..." }                      -> message
 *  { campo: ["error"], non_field_errors } -> fields + message
 */
export function normalizeError(error) {
  if (error?.isDrivlyError) return error;
  const status = error?.response?.status ?? 0;
  const data = error?.response?.data;
  let message = 'No se pudo conectar con el servidor.';
  let fields = {};

  if (data && typeof data === 'object') {
    // Errores de negocio con datos extra, ej. { detail, code: 'SIN_CUPO', cercanos: [...] }
    if (data.detail) message = data.detail;
    else {
      fields = data;
      const first = Object.values(data)[0];
      message = Array.isArray(first) ? first[0] : String(first ?? message);
    }
  } else if (status) {
    message = `Error ${status}`;
  } else if (error?.code === 'ECONNABORTED') {
    message = 'La solicitud tardó demasiado.';
  }
  return { isDrivlyError: true, status, message, fields, code: data?.code, data: data ?? {}, raw: error };
}

export default client;
