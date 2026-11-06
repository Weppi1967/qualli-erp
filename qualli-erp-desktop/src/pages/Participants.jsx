import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { downloadFile, errorMessage, fieldErrors, participantsApi } from '../api/client';
import DynamicForm from '../components/DynamicForm';
import { Alert, Confirm, Empty, Modal, Pagination, Spinner, StatusBadge } from '../components/ui';
import { useDebounced, usePagedList } from '../hooks';
import { useAuth } from '../store/auth';
import { age, ENROLLMENT_STATUS, formatDate, formatDateTime } from '../utils/format';

const EMPTY = { basic_info: {}, address_info: {}, characteristics: {} };

function ParticipantModal({ participant, config, onClose, onSaved }) {
  const { locations, activeLocationId, user } = useAuth();
  const [values, setValues] = useState(
    participant
      ? { basic_info: participant.basic_info, address_info: participant.address_info, characteristics: participant.characteristics }
      : EMPTY,
  );
  const [locationId, setLocationId] = useState(
    participant?.location_id || activeLocationId || user?.location_id || locations[0]?.id || '',
  );
  const [errors, setErrors] = useState({});
  const [error, setError] = useState('');
  const [duplicates, setDuplicates] = useState(null);
  const [busy, setBusy] = useState(false);

  async function save(force = false) {
    setBusy(true);
    setError('');
    setErrors({});
    const body = { ...values, location_id: Number(locationId), force };
    try {
      const saved = participant ? await participantsApi.update(participant.id, body) : await participantsApi.create(body);
      onSaved(saved);
    } catch (e) {
      if (e.response?.status === 409 && e.response.data?.details?.duplicates) {
        setDuplicates(e.response.data.details.duplicates);
      } else {
        setErrors(fieldErrors(e));
        setError(errorMessage(e));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      wide
      title={participant ? `Teilnehmer bearbeiten: ${participant.display_name}` : 'Neuer Teilnehmer'}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-light" onClick={onClose} disabled={busy}>
            Abbrechen
          </button>
          <button className="btn btn-primary" onClick={() => save(false)} disabled={busy || !locationId}>
            {busy ? 'Speichern…' : 'Speichern'}
          </button>
        </>
      }
    >
      <Alert>{error}</Alert>
      {duplicates && (
        <div className="alert alert-warning">
          <div>
            <strong>Mögliche Dublette:</strong>{' '}
            {duplicates.map((d) => `${d.display_name} (${d.location_name})`).join('; ')}
          </div>
          <button className="btn btn-light" onClick={() => save(true)} disabled={busy}>
            Trotzdem anlegen
          </button>
        </div>
      )}
      <div className="form-field">
        <label htmlFor="participant-location">
          Standort<span className="required"> *</span>
        </label>
        <select id="participant-location" value={locationId} onChange={(e) => setLocationId(e.target.value)}>
          {locations.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name}
            </option>
          ))}
        </select>
      </div>
      <DynamicForm config={config} values={values} onChange={setValues} errors={errors} />
    </Modal>
  );
}

function DetailModal({ participant, onClose }) {
  const [history, setHistory] = useState(null);
  const [enrollments, setEnrollments] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    Promise.all([participantsApi.history(participant.id), participantsApi.enrollments(participant.id)])
      .then(([h, e]) => {
        setHistory(h);
        setEnrollments(e);
      })
      .catch((e) => setError(errorMessage(e)));
  }, [participant.id]);

  const ACTIONS = { create: 'Angelegt', update: 'Geändert', delete: 'Gelöscht', restore: 'Wiederhergestellt', import: 'Importiert', batch: 'Batch-Import' };
  return (
    <Modal wide title={participant.display_name} onClose={onClose}>
      <Alert>{error}</Alert>
      <h3>Maßnahmen</h3>
      {!enrollments ? (
        <Spinner />
      ) : enrollments.length === 0 ? (
        <p className="muted">Keine Zuordnungen.</p>
      ) : (
        <table className="table">
          <tbody>
            {enrollments.map((e) => (
              <tr key={e.id}>
                <td>{e.measure_name}</td>
                <td>{formatDate(e.enrollment_date)} – {formatDate(e.exit_date)}</td>
                <td>
                  <StatusBadge status={e.status} labels={ENROLLMENT_STATUS} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <h3>Änderungsverlauf</h3>
      {!history ? (
        <Spinner />
      ) : (
        <ul className="history">
          {history.map((h) => (
            <li key={h.id}>
              <div>
                <strong>{ACTIONS[h.action] || h.action}</strong> · {formatDateTime(h.timestamp)} · {h.changed_by_name || 'System'}
              </div>
              {h.action === 'update' && (
                <ul className="muted small">
                  {Object.entries(h.changes).flatMap(([section, fields]) =>
                    'old' in fields
                      ? [<li key={section}>{section}: {String(fields.old ?? '–')} → {String(fields.new ?? '–')}</li>]
                      : Object.entries(fields).map(([f, c]) => (
                          <li key={`${section}.${f}`}>
                            {f}: {JSON.stringify(c.old) ?? '–'} → {JSON.stringify(c.new) ?? '–'}
                          </li>
                        )),
                  )}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}

export default function Participants() {
  const activeLocationId = useAuth((s) => s.activeLocationId);
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [config, setConfig] = useState(null);
  const [editing, setEditing] = useState(searchParams.get('neu') ? 'new' : null);
  const [detail, setDetail] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const debounced = useDebounced(search);

  useEffect(() => setPage(1), [debounced, activeLocationId]);
  useEffect(() => {
    participantsApi.fields().then(setConfig).catch(() => setConfig(null));
  }, []);

  const fetcher = useCallback((p) => participantsApi.list(p), []);
  const params = { page, per_page: 25, search: debounced || undefined, ...(activeLocationId ? { location_id: activeLocationId } : {}) };
  const { data, loading, error, reload, setError } = usePagedList(fetcher, params);

  function closeEditor() {
    setEditing(null);
    if (searchParams.get('neu')) setSearchParams({});
  }

  async function doDelete() {
    setBusy(true);
    try {
      await participantsApi.remove(deleting.id);
      setNotice(`${deleting.display_name} wurde gelöscht (archiviert).`);
      setDeleting(null);
      reload();
    } catch (e) {
      setError(errorMessage(e));
      setDeleting(null);
    } finally {
      setBusy(false);
    }
  }

  async function exportCsv() {
    try {
      await downloadFile('/reports/participants-export', 'teilnehmer.csv', activeLocationId ? { location_id: activeLocationId } : {});
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Teilnehmerverwaltung</h1>
        <div className="actions">
          <button className="btn btn-light" onClick={exportCsv}>
            CSV-Export
          </button>
          <button className="btn btn-primary" onClick={() => setEditing('new')} disabled={!config}>
            + Neuer Teilnehmer
          </button>
        </div>
      </div>
      <div className="toolbar">
        <input
          className="search"
          type="search"
          placeholder="Suchen: Name, Geburtsdatum, Ort, Telefon, Kundennummer…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Teilnehmer suchen"
        />
      </div>
      <Alert type="success" onClose={() => setNotice('')}>
        {notice}
      </Alert>
      <Alert onClose={() => setError('')}>{error}</Alert>

      <div className="card no-pad">
        {loading && data.items.length === 0 ? (
          <Spinner />
        ) : data.items.length === 0 ? (
          <Empty>{debounced ? 'Keine Treffer.' : 'Noch keine Teilnehmer angelegt.'}</Empty>
        ) : (
          <table className={`table table-hover ${loading ? 'is-loading' : ''}`}>
            <thead>
              <tr>
                <th>Nachname</th>
                <th>Vorname</th>
                <th>Geburtsdatum</th>
                <th>Wohnort</th>
                <th>Standort</th>
                <th className="actions-col">Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((p) => {
                const years = age(p.basic_info.birth_date);
                return (
                  <tr key={p.id} onDoubleClick={() => setEditing(p)}>
                    <td>
                      <strong>{p.basic_info.last_name}</strong>
                    </td>
                    <td>{p.basic_info.first_name}</td>
                    <td>
                      {formatDate(p.basic_info.birth_date)}
                      {years !== null && <span className="muted"> ({years})</span>}
                    </td>
                    <td>{[p.address_info.zip, p.address_info.city].filter(Boolean).join(' ') || '–'}</td>
                    <td>{p.location_name}</td>
                    <td className="actions-col">
                      <button className="btn btn-small btn-light" onClick={() => setDetail(p)}>
                        Details
                      </button>
                      <button className="btn btn-small btn-light" onClick={() => setEditing(p)} disabled={!config}>
                        Bearbeiten
                      </button>
                      <button className="btn btn-small btn-danger-light" onClick={() => setDeleting(p)}>
                        Löschen
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />

      {editing && config && (
        <ParticipantModal
          participant={editing === 'new' ? null : editing}
          config={config}
          onClose={closeEditor}
          onSaved={(saved) => {
            setNotice(`${saved.display_name} wurde gespeichert.`);
            closeEditor();
            reload();
          }}
        />
      )}
      {detail && <DetailModal participant={detail} onClose={() => setDetail(null)} />}
      {deleting && (
        <Confirm
          title="Teilnehmer löschen?"
          message={`${deleting.display_name} wird archiviert (nicht endgültig gelöscht) und verschwindet aus allen Listen.`}
          onConfirm={doDelete}
          onCancel={() => setDeleting(null)}
          busy={busy}
        />
      )}
    </div>
  );
}
