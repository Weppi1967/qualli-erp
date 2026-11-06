import { create } from 'zustand';
import { authApi, tokens } from '../api/client';

const LOCATION_KEY = 'erp.active_location';

export const useAuth = create((set, get) => ({
  user: null,
  locations: [],
  // Standortauswahl: null = alle eigenen Standorte
  activeLocationId: Number(localStorage.getItem(LOCATION_KEY)) || null,
  status: tokens.access ? 'checking' : 'anonymous', // checking | authenticated | anonymous

  async login(username, password) {
    const data = await authApi.login(username, password);
    tokens.set(data.access_token, data.refresh_token);
    await get().loadMe();
  },

  async loadMe() {
    try {
      const { user, locations } = await authApi.me();
      let active = get().activeLocationId;
      if (active && !locations.some((l) => l.id === active)) active = null;
      set({ user, locations, activeLocationId: active, status: 'authenticated' });
    } catch (e) {
      tokens.clear();
      set({ user: null, locations: [], status: 'anonymous' });
      throw e;
    }
  },

  async logout() {
    await authApi.logout();
    get().reset();
  },

  reset() {
    tokens.clear();
    set({ user: null, locations: [], status: 'anonymous' });
  },

  setActiveLocation(id) {
    if (id) localStorage.setItem(LOCATION_KEY, String(id));
    else localStorage.removeItem(LOCATION_KEY);
    set({ activeLocationId: id || null });
  },

  can(action) {
    const role = get().user?.role;
    if (action === 'manageMeasures') return role === 'admin' || role === 'location_manager';
    if (action === 'admin') return role === 'admin';
    return Boolean(role);
  },
}));

/** Query-Parameter für den aktuell gewählten Standort. */
export function locationParams() {
  const id = useAuth.getState().activeLocationId;
  return id ? { location_id: id } : {};
}
