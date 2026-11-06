import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi, errorMessage } from '../api/client';
import { Alert } from '../components/ui';
import { useAuth } from '../store/auth';
import { formatDateTime, ROLE_LABELS } from '../utils/format';

function PasswordForm() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [repeat, setRepeat] = useState('');
  const [msg, setMsg] = useState({ type: '', text: '' });

  async function submit(e) {
    e.preventDefault();
    if (next !== repeat) {
      setMsg({ type: 'error', text: 'Die neuen Passwörter stimmen nicht überein.' });
      return;
    }
    try {
      await authApi.changePassword(current, next);
      setMsg({ type: 'success', text: 'Passwort geändert.' });
      setCurrent('');
      setNext('');
      setRepeat('');
    } catch (err) {
      setMsg({ type: 'error', text: errorMessage(err) });
    }
  }

  return (
    <form onSubmit={submit} className="form-grid">
      <div className="span-2">
        <Alert type={msg.type} onClose={() => setMsg({})}>
          {msg.text}
        </Alert>
      </div>
      <div className="form-field span-2">
        <label htmlFor="pw-current">Aktuelles Passwort</label>
        <input id="pw-current" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
      </div>
      <div className="form-field">
        <label htmlFor="pw-new">Neues Passwort (min. 8 Zeichen)</label>
        <input id="pw-new" type="password" autoComplete="new-password" minLength={8} value={next} onChange={(e) => setNext(e.target.value)} required />
      </div>
      <div className="form-field">
        <label htmlFor="pw-repeat">Wiederholen</label>
        <input id="pw-repeat" type="password" autoComplete="new-password" minLength={8} value={repeat} onChange={(e) => setRepeat(e.target.value)} required />
      </div>
      <div>
        <button className="btn btn-primary">Passwort ändern</button>
      </div>
    </form>
  );
}

export default function Settings() {
  const { user, locations, activeLocationId, setActiveLocation, logout } = useAuth();
  const navigate = useNavigate();
  const [info, setInfo] = useState(null);
  const [restartMsg, setRestartMsg] = useState('');

  useEffect(() => {
    window.erp?.getInfo().then(setInfo).catch(() => setInfo(null));
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1>Einstellungen</h1>
      </div>
      <div className="two-col">
        <section className="card">
          <h2>Angemeldet als</h2>
          <dl className="dl">
            <dt>Benutzer</dt>
            <dd>{user?.username}</dd>
            <dt>Name</dt>
            <dd>{user?.full_name || '–'}</dd>
            <dt>Rolle</dt>
            <dd>{ROLE_LABELS[user?.role]}</dd>
            <dt>E-Mail</dt>
            <dd>{user?.email || '–'}</dd>
            <dt>Letzte Anmeldung</dt>
            <dd>{formatDateTime(user?.last_login_at)}</dd>
          </dl>
          <button
            className="btn btn-danger"
            onClick={async () => {
              await logout();
              navigate('/login');
            }}
          >
            Abmelden
          </button>
        </section>

        <section className="card">
          <h2>Standort-Auswahl</h2>
          <p className="muted">Begrenzt Listen auf einen Standort. „Alle“ zeigt alle Standorte, auf die Sie Zugriff haben.</p>
          <div className="radio-list">
            {locations.length > 1 && (
              <label>
                <input type="radio" name="loc" checked={!activeLocationId} onChange={() => setActiveLocation(null)} />
                Alle Standorte
              </label>
            )}
            {locations.map((l) => (
              <label key={l.id}>
                <input type="radio" name="loc" checked={activeLocationId === l.id} onChange={() => setActiveLocation(l.id)} />
                {l.name}
              </label>
            ))}
          </div>
        </section>

        <section className="card">
          <h2>Passwort ändern</h2>
          <PasswordForm />
        </section>

        <section className="card">
          <h2>System</h2>
          {info ? (
            <>
              <dl className="dl">
                <dt>App-Version</dt>
                <dd>{info.appVersion}</dd>
                <dt>Backend</dt>
                <dd>
                  {info.backendUrl} – {info.backendOnline ? 'online ✅' : 'offline ❌'}
                </dd>
                <dt>Backend gestartet von</dt>
                <dd>{info.backendManaged ? 'Desktop-App' : 'extern (bereits laufend)'}</dd>
                <dt>Programmordner</dt>
                <dd className="small">{info.projectRoot}</dd>
              </dl>
              {info.backendManaged && (
                <button
                  className="btn btn-light"
                  onClick={async () => {
                    setRestartMsg('Neustart…');
                    const ok = await window.erp.restartBackend();
                    setRestartMsg(ok ? 'Backend neu gestartet.' : 'Neustart fehlgeschlagen.');
                  }}
                >
                  Backend neu starten
                </button>
              )}
              {restartMsg && <p className="muted">{restartMsg}</p>}
            </>
          ) : (
            <p className="muted">Läuft im Browser (nicht in der Desktop-App).</p>
          )}
        </section>
      </div>
    </div>
  );
}
