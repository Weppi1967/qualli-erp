import { useState } from 'react';
import { errorMessage, importApi } from '../api/client';
import { Alert } from '../components/ui';
import { useAuth } from '../store/auth';

function Result({ result }) {
  return (
    <section className="card">
      <h2>{result.dry_run ? 'Prüfergebnis (noch nichts gespeichert)' : 'Import abgeschlossen'}</h2>
      <div className="stats-grid small-stats">
        <div className="stat-card">
          <div className="stat-value">{result.total_rows}</div>
          <div className="stat-label">Zeilen</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{result.created}</div>
          <div className="stat-label">{result.dry_run ? 'würden angelegt' : 'angelegt'}</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{result.duplicates.length}</div>
          <div className="stat-label">Dubletten</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{result.errors.length}</div>
          <div className="stat-label">Fehler</div>
        </div>
      </div>
      <h3>Spaltenzuordnung</h3>
      <table className="table">
        <tbody>
          {Object.entries(result.column_mapping).map(([col, target]) => (
            <tr key={col}>
              <td>{col}</td>
              <td className="muted">→ {target === 'location' ? 'Standort' : target}</td>
            </tr>
          ))}
          {result.unmapped_columns.map((col) => (
            <tr key={col}>
              <td>{col}</td>
              <td className="muted">→ nicht erkannt, wird unter „Zusatzfelder“ gespeichert</td>
            </tr>
          ))}
        </tbody>
      </table>
      {result.duplicates.length > 0 && (
        <>
          <h3>Dubletten (übersprungen)</h3>
          <ul className="list">
            {result.duplicates.map((d) => (
              <li key={d.row}>
                <span>
                  Zeile {d.row}: {d.name}
                </span>
                <span className="muted">{d.reason}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {result.errors.length > 0 && (
        <>
          <h3>Fehler</h3>
          <ul className="list">
            {result.errors.map((e) => (
              <li key={e.row}>
                <span>Zeile {e.row}</span>
                <span className="error-text">{e.error}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {result.warnings?.length > 0 && (
        <>
          <h3>Hinweise</h3>
          <ul className="list">
            {result.warnings.map((w) => (
              <li key={w.row}>
                <span>Zeile {w.row}</span>
                <span className="muted">{w.warning} – Originalwert wurde in Zusatzfeldern gesichert</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

export default function Import() {
  const { locations, activeLocationId, user } = useAuth();
  const [file, setFile] = useState(null);
  const [locationId, setLocationId] = useState(activeLocationId || user?.location_id || locations[0]?.id || '');
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function run(dryRun) {
    setBusy(true);
    setError('');
    try {
      setResult(await importApi.qualliLife(file, { locationId, dryRun, skipDuplicates }));
    } catch (e) {
      setError(errorMessage(e));
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Import aus Qualli.life</h1>
      </div>
      <section className="card">
        <p>
          Export aus Qualli.life als <strong>CSV oder Excel (.xlsx)</strong> hochladen. Spalten wie „Vorname“, „Nachname“,
          „Geburtsdatum“, „PLZ“, „Ort“ werden automatisch erkannt. Eine Spalte „Standort“ in der Datei hat Vorrang vor der Auswahl
          unten. Maximal 1000 Zeilen pro Datei.
        </p>
        <div className="form-grid">
          <div className="form-field">
            <label htmlFor="import-file">Datei</label>
            <input
              id="import-file"
              type="file"
              accept=".csv,.xlsx,.xlsm,.txt"
              onChange={(e) => {
                setFile(e.target.files[0] || null);
                setResult(null);
              }}
            />
          </div>
          <div className="form-field">
            <label htmlFor="import-location">Standard-Standort</label>
            <select id="import-location" value={locationId} onChange={(e) => setLocationId(e.target.value)}>
              {locations.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </div>
          <label className="checkbox span-2">
            <input type="checkbox" checked={skipDuplicates} onChange={(e) => setSkipDuplicates(e.target.checked)} />
            Dubletten (gleicher Vor- und Nachname) überspringen
          </label>
        </div>
        <div className="actions">
          <button className="btn btn-light" disabled={!file || busy} onClick={() => run(true)}>
            1. Prüfen
          </button>
          <button className="btn btn-primary" disabled={!file || busy || !result?.dry_run} onClick={() => run(false)} title={!result?.dry_run ? 'Bitte zuerst prüfen' : ''}>
            2. Importieren
          </button>
        </div>
      </section>
      <Alert>{error}</Alert>
      {result && <Result result={result} />}
    </div>
  );
}
