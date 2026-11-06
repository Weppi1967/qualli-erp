import { useEffect } from 'react';

export function Modal({ title, onClose, children, footer, wide = false }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose?.();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className={`modal ${wide ? 'modal-wide' : ''}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Schließen">
            ×
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}

export function Pagination({ page, pages, total, onChange }) {
  if (!total) return null;
  return (
    <div className="pagination">
      <span className="muted">{total} Einträge</span>
      <div className="pagination-buttons">
        <button className="btn btn-light" disabled={page <= 1} onClick={() => onChange(page - 1)}>
          ‹ Zurück
        </button>
        <span>
          Seite {page} von {pages}
        </span>
        <button className="btn btn-light" disabled={page >= pages} onClick={() => onChange(page + 1)}>
          Weiter ›
        </button>
      </div>
    </div>
  );
}

export function Alert({ type = 'error', children, onClose }) {
  if (!children) return null;
  return (
    <div className={`alert alert-${type}`} role={type === 'error' ? 'alert' : 'status'}>
      <span>{children}</span>
      {onClose && (
        <button className="icon-btn" onClick={onClose} aria-label="Meldung schließen">
          ×
        </button>
      )}
    </div>
  );
}

export function Spinner({ label = 'Lädt…' }) {
  return (
    <div className="spinner-wrap" role="status">
      <span className="spinner" /> {label}
    </div>
  );
}

export function StatusBadge({ status, labels }) {
  return <span className={`badge badge-${status}`}>{labels?.[status] || status}</span>;
}

export function Empty({ children }) {
  return <div className="empty">{children}</div>;
}

export function Confirm({ title, message, confirmLabel = 'Löschen', onConfirm, onCancel, busy }) {
  return (
    <Modal
      title={title}
      onClose={onCancel}
      footer={
        <>
          <button className="btn btn-light" onClick={onCancel} disabled={busy}>
            Abbrechen
          </button>
          <button className="btn btn-danger" onClick={onConfirm} disabled={busy}>
            {busy ? 'Bitte warten…' : confirmLabel}
          </button>
        </>
      }
    >
      <p>{message}</p>
    </Modal>
  );
}
