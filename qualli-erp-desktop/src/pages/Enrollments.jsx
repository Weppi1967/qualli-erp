import { useCallback, useEffect, useState } from 'react';
import { enrollmentsApi, errorMessage, measuresApi, participantsApi } from '../api/client';
import { Alert, Confirm, Empty, Spinner, StatusBadge } from '../components/ui';
import { useDebounced, usePagedList } from '../hooks';
import { useAuth } from '../store/auth';
import { ENROLLMENT_STATUS, formatDate, MEASURE_STATUS } from '../utils/format';

const today = () => new Date().toISOString().slice(0, 10);

function ParticipantPicker({ selected, onSelect }) {
  const activeLocationId = useAuth((s) => s.activeLocationId);
  const [search, setSearch] = useState('');
  const debounced = useDebounced(search);
  const fetcher = useCallback((p) => participantsApi.list(p), []);
  const { data, loading, error } = usePagedList(fetcher, {
    per_page: 50,
    search: debounced || undefined,
    ...(activeLocationId ? { location_id: activeLocationId } : {}),
  });

  return (
    <section className="card picker">
      <h2>1. Teilnehmer auswählen</h2>
      <input className="search" type="search" placeholder="Name suchen…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Teilnehmer suchen" />
      <Alert>{error}</Alert>
      {loading && data.items.length === 0 && <Spinner />}
      <ul className="pick-list">
        {data.items.map((p) => (
          <li key={p.id}>
            <button className={selected?.id === p.id ? 'active' : ''} onClick={() => onSelect(p)}>
              <span>{p.display_name}</span>
              <span className="muted small">{p.location_name}</span>
            </button>
          </li>
        ))}
      </ul>
      {data.total > data.items.length && <p className="muted small">{data.total - data.items.length} weitere – bitte Suche verfeinern.</p>}
    </section>
  );
}

export default function Enrollments() {
  const [participant, setParticipant] = useState(null);
  const [enrollments, setEnrollments] = useState(null);
  const [measures, setMeasures] = useState([]);
  const [entryDate, setEntryDate] = useState(today());
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [removing, setRemoving] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (p) => {
    if (!p) return;
    setEnrollments(null);
    setError('');
    try {
      const [items, ms] = await Promise.all([
        participantsApi.enrollments(p.id),
        measuresApi.list({ location_id: p.location_id, status: 'aktiv,geplant', per_page: 200 }),
      ]);
      setEnrollments(items);
      setMeasures(ms.items);
    } catch (e) {
      setError(errorMessage(e));
      setEnrollments([]);
    }
  }, []);

  useEffect(() => {
    load(participant);
  }, [participant, load]);

  const activeMeasureIds = new Set((enrollments || []).filter((e) => e.status === 'aktiv').map((e) => e.measure_id));
  const available = measures.filter((m) => !activeMeasureIds.has(m.id));

  async function add(measure) {
    setBusy(true);
    setError('');
    try {
      await enrollmentsApi.create({ participant_id: participant.id, measure_id: measure.id, enrollment_date: entryDate });
      setNotice(`${participant.display_name} wurde „${measure.name}“ zugeordnet.`);
      await load(participant);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(enrollment, status) {
    setError('');
    try {
      await enrollmentsApi.update(enrollment.id, { status });
      await load(participant);
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await enrollmentsApi.remove(removing.id);
      setNotice('Zuordnung entfernt.');
      setRemoving(null);
      await load(participant);
    } catch (e) {
      setError(errorMessage(e));
      setRemoving(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Zuordnungen</h1>
        <p className="muted">Teilnehmer ↔ Maßnahme</p>
      </div>
      <Alert type="success" onClose={() => setNotice('')}>
        {notice}
      </Alert>
      <Alert onClose={() => setError('')}>{error}</Alert>
      <div className="enroll-layout">
        <ParticipantPicker selected={participant} onSelect={setParticipant} />
        <div className="stack">
          {!participant ? (
            <section className="card">
              <Empty>Links einen Teilnehmer auswählen.</Empty>
            </section>
          ) : (
            <>
              <section className="card">
                <h2>Maßnahmen von {participant.display_name}</h2>
                {!enrollments ? (
                  <Spinner />
                ) : enrollments.length === 0 ? (
                  <p className="muted">Noch keine Zuordnungen.</p>
                ) : (
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Maßnahme</th>
                        <th>Eintritt</th>
                        <th>Austritt</th>
                        <th>Status</th>
                        <th className="actions-col" />
                      </tr>
                    </thead>
                    <tbody>
                      {enrollments.map((e) => (
                        <tr key={e.id}>
                          <td>
                            {e.measure_name} <span className="muted small">({e.location_name})</span>
                          </td>
                          <td>{formatDate(e.enrollment_date)}</td>
                          <td>{formatDate(e.exit_date)}</td>
                          <td>
                            <select value={e.status} onChange={(ev) => changeStatus(e, ev.target.value)} aria-label="Status ändern" className={`status-select badge-${e.status}`}>
                              {Object.entries(ENROLLMENT_STATUS).map(([v, l]) => (
                                <option key={v} value={v}>
                                  {l}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="actions-col">
                            <button className="btn btn-small btn-danger-light" onClick={() => setRemoving(e)}>
                              Entfernen
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>
              <section className="card">
                <div className="card-header">
                  <h2>2. Verfügbare Maßnahmen ({participant.location_name})</h2>
                  <label className="inline-field">
                    Eintrittsdatum
                    <input type="date" value={entryDate} onChange={(e) => setEntryDate(e.target.value)} />
                  </label>
                </div>
                {available.length === 0 ? (
                  <p className="muted">Keine weiteren aktiven oder geplanten Maßnahmen an diesem Standort.</p>
                ) : (
                  <table className="table">
                    <tbody>
                      {available.map((m) => (
                        <tr key={m.id}>
                          <td>
                            <strong>{m.name}</strong>
                            <div className="muted small">
                              {formatDate(m.start_date)} – {formatDate(m.end_date)}
                            </div>
                          </td>
                          <td>
                            <StatusBadge status={m.status} labels={MEASURE_STATUS} />
                          </td>
                          <td className="num">
                            {m.active_enrollments}
                            {m.capacity ? ` / ${m.capacity}` : ''} belegt
                          </td>
                          <td className="actions-col">
                            <button className="btn btn-small btn-primary" disabled={busy} onClick={() => add(m)}>
                              Hinzufügen
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>
            </>
          )}
        </div>
      </div>
      {removing && (
        <Confirm
          title="Zuordnung entfernen?"
          message={`Zuordnung zu „${removing.measure_name}“ entfernen? Tipp: Für normale Austritte besser den Status auf „Beendet“ oder „Abgebrochen“ setzen.`}
          confirmLabel="Entfernen"
          onConfirm={remove}
          onCancel={() => setRemoving(null)}
          busy={busy}
        />
      )}
    </div>
  );
}
