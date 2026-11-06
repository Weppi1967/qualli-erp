import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { dashboardApi, errorMessage } from '../api/client';
import { Alert, Spinner } from '../components/ui';
import { useAuth } from '../store/auth';
import { formatDate } from '../utils/format';

function Stat({ label, value, sub, to }) {
  const body = (
    <>
      <div className="stat-value">{value ?? '–'}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </>
  );
  return to ? (
    <Link to={to} className="stat-card">
      {body}
    </Link>
  ) : (
    <div className="stat-card">{body}</div>
  );
}

function greeting() {
  const h = new Date().getHours();
  if (h < 11) return 'Guten Morgen';
  if (h < 18) return 'Guten Tag';
  return 'Guten Abend';
}

export default function Dashboard() {
  const user = useAuth((s) => s.user);
  const [stats, setStats] = useState(null);
  const [locations, setLocations] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([dashboardApi.stats(), dashboardApi.locations()])
      .then(([s, l]) => {
        setStats(s);
        setLocations(l);
      })
      .catch((e) => setError(errorMessage(e)));
  }, []);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>
            {greeting()}, {user?.full_name || user?.username}!
          </h1>
          <p className="muted">Überblick über alle Ihre Standorte.</p>
        </div>
        <div className="actions">
          <Link className="btn btn-primary" to="/teilnehmer?neu=1">
            + Teilnehmer anlegen
          </Link>
          <Link className="btn btn-light" to="/zuordnungen">
            Zuordnung vornehmen
          </Link>
        </div>
      </div>
      <Alert>{error}</Alert>
      {!stats && !error && <Spinner />}
      {stats && (
        <>
          <div className="stats-grid">
            <Stat label="Teilnehmer" value={stats.participants_total} sub={`+${stats.participants_new_30d} in 30 Tagen`} to="/teilnehmer" />
            <Stat label="davon in aktiver Maßnahme" value={stats.participants_in_active_measure} to="/zuordnungen" />
            <Stat label="Aktive Maßnahmen" value={stats.measures_by_status.aktiv} sub={`${stats.measures_by_status.geplant} geplant · ${stats.measures_by_status.beendet} beendet`} to="/massnahmen" />
            <Stat label="Aktive Zuordnungen" value={stats.enrollments_by_status.aktiv} sub={`${stats.enrollments_by_status.abgebrochen} abgebrochen`} />
          </div>

          <div className="two-col">
            <section className="card">
              <h2>Standorte</h2>
              <table className="table">
                <thead>
                  <tr>
                    <th>Standort</th>
                    <th className="num">Teilnehmer</th>
                    <th className="num">Aktive Maßn.</th>
                    <th className="num">Aktive Zuordn.</th>
                  </tr>
                </thead>
                <tbody>
                  {locations.map((l) => (
                    <tr key={l.id}>
                      <td>{l.name}</td>
                      <td className="num">{l.participants}</td>
                      <td className="num">{l.measures_active}</td>
                      <td className="num">{l.enrollments_active}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
            <div className="stack">
              <section className="card">
                <h2>Maßnahmen enden in 30 Tagen</h2>
                {stats.measures_ending_soon.length === 0 && <p className="muted">Keine.</p>}
                <ul className="list">
                  {stats.measures_ending_soon.map((m) => (
                    <li key={m.id}>
                      <span>{m.name}</span>
                      <span className="muted">{formatDate(m.end_date)}</span>
                    </li>
                  ))}
                </ul>
              </section>
              <section className="card">
                <h2>Zuletzt angelegt</h2>
                {stats.recent_participants.length === 0 && <p className="muted">Noch keine Teilnehmer.</p>}
                <ul className="list">
                  {stats.recent_participants.map((p) => (
                    <li key={p.id}>
                      <span>{p.display_name}</span>
                      <span className="muted">{p.location_name}</span>
                    </li>
                  ))}
                </ul>
              </section>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
