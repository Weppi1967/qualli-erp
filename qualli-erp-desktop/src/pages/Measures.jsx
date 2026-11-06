import { useCallback, useEffect, useState } from 'react';
import { downloadFile, errorMessage, measuresApi } from '../api/client';
import { Alert, Confirm, Empty, Modal, Pagination, Spinner, StatusBadge } from '../components/ui';
import { useDebounced, usePagedList } from '../hooks';
import { useAuth } from '../store/auth';
import { formatDate, MEASURE_STATUS } from '../utils/format';

function MeasureModal({ measure, onClose, onSaved }) {
  const { locations, activeLocationId, user } = useAuth();
  const [form, setForm] = useState({
    name: measure?.name || '',
    number: measure?.number || '',
    location_id: measure?.location_id || activeLocationId || user?.location_id || locations[0]?.id || '',
    status: measure?.status || 'geplant',
    start_date: measure?.start_date || '',
    end_date: measure?.end_date || '',
    capacity: measure?.capacity ?? '',
    description: measure?.description || '',
  });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function save(e) {
    e?.preventDefault();
    setBusy(true);
    setError('');
    try {
      const body = { ...form, location_id: Number(form.location_id) };
      const saved = measure ? await measuresApi.update(measure.id, body) : await measuresApi.create(body);
      onSaved(saved);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={measure ? 'Maßnahme bearbeiten' : 'Neue Maßnahme'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-light" onClick={onClose} disabled={busy}>
            Abbrechen
          </button>
          <button className="btn btn-primary" onClick={save} disabled={busy}>
            {busy ? 'Speichern…' : 'Speichern'}
          </button>
        </>
      }
    >
      <Alert>{error}</Alert>
      <form className="form-grid" onSubmit={save}>
        <div className="form-field span-2">
          <label htmlFor="m-name">
            Bezeichnung<span className="required"> *</span>
          </label>
          <input id="m-name" value={form.name} onChange={set('name')} required autoFocus />
        </div>
        <div className="form-field">
          <label htmlFor="m-number">Maßnahmenummer</label>
          <input id="m-number" value={form.number} onChange={set('number')} />
        </div>
        <div className="form-field">
          <label htmlFor="m-location">Standort</label>
          <select id="m-location" value={form.location_id} onChange={set('location_id')}>
            {locations.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="m-status">Status</label>
          <select id="m-status" value={form.status} onChange={set('status')}>
            {Object.entries(MEASURE_STATUS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </div>
        <div className="form-field">
          <label htmlFor="m-capacity">Plätze</label>
          <input id="m-capacity" type="number" min="0" value={form.capacity} onChange={set('capacity')} />
        </div>
        <div className="form-field">
          <label htmlFor="m-start">Beginn</label>
          <input id="m-start" type="date" value={form.start_date} onChange={set('start_date')} />
        </div>
        <div className="form-field">
          <label htmlFor="m-end">Ende</label>
          <input id="m-end" type="date" value={form.end_date} onChange={set('end_date')} />
        </div>
        <div className="form-field span-2">
          <label htmlFor="m-desc">Beschreibung</label>
          <textarea id="m-desc" rows={3} value={form.description} onChange={set('description')} />
        </div>
      </form>
    </Modal>
  );
}

export default function Measures() {
  const { activeLocationId, can } = useAuth();
  const canManage = can('manageMeasures');
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const debounced = useDebounced(search);

  useEffect(() => setPage(1), [status, debounced, activeLocationId]);
  const fetcher = useCallback((p) => measuresApi.list(p), []);
  const params = {
    page,
    per_page: 25,
    status: status || undefined,
    search: debounced || undefined,
    ...(activeLocationId ? { location_id: activeLocationId } : {}),
  };
  const { data, loading, error, reload, setError } = usePagedList(fetcher, params);

  async function doDelete() {
    setBusy(true);
    try {
      await measuresApi.remove(deleting.id);
      setNotice(`„${deleting.name}“ wurde gelöscht (archiviert).`);
      setDeleting(null);
      reload();
    } catch (e) {
      setError(errorMessage(e));
      setDeleting(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Maßnahmenverwaltung</h1>
        <div className="actions">
          <button
            className="btn btn-light"
            onClick={() =>
              downloadFile('/reports/measures-summary', 'massnahmen.csv', {
                format: 'csv',
                ...(activeLocationId ? { location_id: activeLocationId } : {}),
              }).catch((e) => setError(errorMessage(e)))
            }
          >
            CSV-Übersicht
          </button>
          {canManage && (
            <button className="btn btn-primary" onClick={() => setEditing('new')}>
              + Neue Maßnahme
            </button>
          )}
        </div>
      </div>
      <div className="toolbar">
        <div className="segmented" role="group" aria-label="Status-Filter">
          {[['', 'Alle'], ...Object.entries(MEASURE_STATUS)].map(([v, l]) => (
            <button key={v} className={status === v ? 'active' : ''} onClick={() => setStatus(v)} aria-pressed={status === v}>
              {l}
            </button>
          ))}
        </div>
        <input className="search" type="search" placeholder="Name oder Nummer suchen…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Maßnahmen suchen" />
      </div>
      <Alert type="success" onClose={() => setNotice('')}>
        {notice}
      </Alert>
      <Alert onClose={() => setError('')}>{error}</Alert>

      <div className="card no-pad">
        {loading && data.items.length === 0 ? (
          <Spinner />
        ) : data.items.length === 0 ? (
          <Empty>Keine Maßnahmen gefunden.</Empty>
        ) : (
          <table className={`table table-hover ${loading ? 'is-loading' : ''}`}>
            <thead>
              <tr>
                <th>Maßnahme</th>
                <th>Nummer</th>
                <th>Standort</th>
                <th>Zeitraum</th>
                <th className="num">Belegung</th>
                <th>Status</th>
                {canManage && <th className="actions-col">Aktionen</th>}
              </tr>
            </thead>
            <tbody>
              {data.items.map((m) => (
                <tr key={m.id} onDoubleClick={() => canManage && setEditing(m)}>
                  <td>
                    <strong>{m.name}</strong>
                  </td>
                  <td>{m.number || '–'}</td>
                  <td>{m.location_name}</td>
                  <td>
                    {formatDate(m.start_date)} – {formatDate(m.end_date)}
                  </td>
                  <td className="num">
                    {m.active_enrollments}
                    {m.capacity ? ` / ${m.capacity}` : ''}
                  </td>
                  <td>
                    <StatusBadge status={m.status} labels={MEASURE_STATUS} />
                  </td>
                  {canManage && (
                    <td className="actions-col">
                      <button className="btn btn-small btn-light" onClick={() => setEditing(m)}>
                        Bearbeiten
                      </button>
                      <button className="btn btn-small btn-danger-light" onClick={() => setDeleting(m)}>
                        Löschen
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />

      {editing && (
        <MeasureModal
          measure={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(m) => {
            setNotice(`„${m.name}“ wurde gespeichert.`);
            setEditing(null);
            reload();
          }}
        />
      )}
      {deleting && (
        <Confirm
          title="Maßnahme löschen?"
          message={`„${deleting.name}“ wird archiviert und verschwindet zusammen mit ihren Zuordnungen aus den Listen.`}
          onConfirm={doDelete}
          onCancel={() => setDeleting(null)}
          busy={busy}
        />
      )}
    </div>
  );
}
