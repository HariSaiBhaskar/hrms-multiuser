import axios from "axios";

const BASE = import.meta.env.VITE_API_BASE || "/api";

const ACCESS_KEY = "hrms.access";
const REFRESH_KEY = "hrms.refresh";

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set({ access, refresh }) {
    if (access) localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

const api = axios.create({ baseURL: BASE, timeout: 20000 });

api.interceptors.request.use((config) => {
  const token = tokens.access;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Transparently refresh the access token once, then replay the request.
let refreshing = null;

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { response, config } = error;
    const isAuthCall = config?.url?.includes("/auth/login") || config?.url?.includes("/auth/refresh");

    if (response?.status === 401 && !config._retried && !isAuthCall && tokens.refresh) {
      config._retried = true;
      try {
        refreshing =
          refreshing ||
          axios.post(`${BASE}/auth/refresh/`, { refresh: tokens.refresh }).finally(() => {
            refreshing = null;
          });
        const { data } = await refreshing;
        tokens.set({ access: data.access, refresh: data.refresh });
        config.headers.Authorization = `Bearer ${data.access}`;
        return api(config);
      } catch {
        tokens.clear();
        window.location.assign("/login");
      }
    }
    return Promise.reject(error);
  }
);

/** Turn any axios failure into a single readable string. */
export function errorMessage(error) {
  const data = error?.response?.data;
  if (!data) return error?.message || "Network error - is the backend running?";
  if (data.errors && Object.keys(data.errors).length) {
    const first = Object.entries(data.errors)[0];
    const value = Array.isArray(first[1]) ? first[1][0] : first[1];
    return `${first[0]}: ${value}`;
  }
  if (Array.isArray(data)) return data[0];
  return data.detail || "Something went wrong.";
}

export function fieldErrors(error) {
  return error?.response?.data?.errors || {};
}

export default api;
