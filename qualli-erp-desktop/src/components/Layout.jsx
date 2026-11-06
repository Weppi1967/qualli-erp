import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../store/auth';
import { ROLE_LABELS } from '../utils/format';

const NAV = [
  { to: '/', label: 'Dashboard', icon: '📊', end: true },
  { to: '/teilnehmer', label: 'Teilnehmer', icon: '👥' },
  { to: '/massnahmen', label: 'Maßnahmen', icon: '📚' },
  { to: '/zuordnungen', label: 'Zuordnungen', icon: '🔗' },
  { to: '/import', label: 'Import', icon: '📥' },
  { to: '/einstellungen', label: 'Einstellungen', icon: '⚙️' },
];

export default function Layout() {
  const { user, locations, activeLocationId, setActiveLocation, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-title">Qualli-ERP</div>
          <div className="brand-sub">Profilingbüro Glaser</div>
        </div>
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              <span className="nav-icon" aria-hidden="true">
                {n.icon}
              </span>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-name">{user?.full_name || user?.username}</div>
          <div className="muted small">{ROLE_LABELS[user?.role]}</div>
          <button
            className="btn btn-ghost"
            onClick={async () => {
              await logout();
              navigate('/login');
            }}
          >
            Abmelden
          </button>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <label className="location-select">
            <span>Standort:</span>
            <select
              value={activeLocationId || ''}
              onChange={(e) => setActiveLocation(Number(e.target.value) || null)}
              disabled={locations.length <= 1}
            >
              {locations.length > 1 && <option value="">Alle Standorte ({locations.length})</option>}
              {locations.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </label>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
