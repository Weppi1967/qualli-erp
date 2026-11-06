// HTTP-Client: alle API-Aufrufe mit JWT Bearer Token, automatischer Token-Refresh.
import axios from 'axios';

const ACCESS_KEY = 'erp.access_token';
const REFRESH_KEY = 'erp.refresh_token';

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set(access, refresh) {
    if (access) localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

// Gleiche Origin: im Dev-Modus über den Vite-Proxy, sonst liefert Flask die App aus.
export const api = axios.create({ baseURL: '/api', timeout: 30000 });

let onSessionExpired = () => {};
export function setSessionExpiredHandler(fn) {
  onSessionExpired = fn;
}

api.interceptors.request.use((config) => {
  const token = tokens.access;
  if (token && !config.headers.Authorization) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshPromise = null;
async function refreshAccessToken() {
  if (!tokens.refresh) throw new Error('kein Refresh-Token');
  if (!refreshPromise) {
    refreshPromise = axios
      .post('/api/auth/refresh', null, { headers: { Authorization: `Bearer ${tokens.refresh}` } })
      .then((res) => {
        tokens.set(res.data.access_token);
        return res.data.access_token;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config || {};
    const status = error.response?.status;
    const code = error.response?.data?.code;
    const isAuthCall = original.url?.startsWith('/auth/login') || original.url?.startsWith('/auth/refresh');
    if (status === 401 && !original._retried && !isAuthCall && code === 'token_expired') {
      original._retried = true;
      try {
        const token = await refreshAccessToken();
        original.headers = { ...original.headers, Authorization: `Bearer ${token}` };
        return api(original);
      } catch {
        /* fällt durch zu Session-Ende */
      }
    }
    if (status === 401 && !isAuthCall) {
      tokens.clear();
      onSessionExpired();
    }
    return Promise.reject(error);
  },
);

/** Lesbare deutsche Fehlermeldung aus einer Axios-Fehlerantwort. */
export function errorMessage(error, fallback = 'Unbekannter Fehler') {
  if (!error) return fallback;
  if (error.response) {
    const data = error.response.data;
    if (data && typeof data === 'object' && data.error) return data.error;
    return `Fehler ${error.response.status}`;
  }
  if (error.code === 'ECONNABORTED') return 'Zeitüberschreitung – der Server antwortet nicht.';
  if (error.request) return 'Keine Verbindung zum Backend. Läuft der Server?';
  return error.message || fallback;
}

/** Feldfehler (details) einer 422-Antwort, z.B. {"basic_info.last_name": "..."} */
export function fieldErrors(error) {
  const details = error?.response?.data?.details;
  return details && typeof details === 'object' && !Array.isArray(details) ? details : {};
}

export async function downloadFile(url, fallbackName, params) {
  const res = await api.get(url, { responseType: 'blob', params });
  const disposition = res.headers['content-disposition'] || '';
  const match = /filename="?([^";]+)"?/.exec(disposition);
  const name = match ? match[1] : fallbackName;
  const href = URL.createObjectURL(res.data);
  const a = document.createElement('a');
  a.href = href;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}

// ---- Endpunkte ----
export const authApi = {
  login: (username, password) => api.post('/auth/login', { username, password }).then((r) => r.data),
  me: () => api.get('/auth/me').then((r) => r.data),
  logout: () => api.post('/auth/logout', { refresh_token: tokens.refresh }).catch(() => null),
  changePassword: (current_password, new_password) =>
    api.post('/auth/change-password', { current_password, new_password }).then((r) => r.data),
};

const crud = (base) => ({
  list: (params) => api.get(base, { params }).then((r) => r.data),
  get: (id) => api.get(`${base}/${id}`).then((r) => r.data),
  create: (body) => api.post(base, body).then((r) => r.data),
  update: (id, body) => api.put(`${base}/${id}`, body).then((r) => r.data),
  remove: (id) => api.delete(`${base}/${id}`).then((r) => r.data),
});

export const participantsApi = {
  ...crud('/participants'),
  fields: () => api.get('/participants/config/fields').then((r) => r.data),
  history: (id) => api.get(`/participants/${id}/history`).then((r) => r.data.items),
  enrollments: (id) => api.get(`/participants/${id}/enrollments`).then((r) => r.data.items),
  restore: (id) => api.post(`/participants/${id}/restore`).then((r) => r.data),
};
export const measuresApi = crud('/measures');
export const enrollmentsApi = crud('/enrollments');
export const dashboardApi = {
  stats: () => api.get('/dashboard/stats').then((r) => r.data),
  locations: () => api.get('/dashboard/locations').then((r) => r.data.items),
};
export const importApi = {
  qualliLife: (file, { locationId, dryRun, skipDuplicates = true }) => {
    const form = new FormData();
    form.append('file', file);
    if (locationId) form.append('location_id', String(locationId));
    form.append('dry_run', dryRun ? '1' : '0');
    form.append('skip_duplicates', skipDuplicates ? '1' : '0');
    return api.post('/import/qualli-life', form, { timeout: 120000 }).then((r) => r.data);
  },
};
