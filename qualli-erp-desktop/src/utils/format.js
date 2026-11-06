export const ROLE_LABELS = {
  admin: 'Administrator',
  location_manager: 'Standortleitung',
  employee: 'Mitarbeiter:in',
};

export const MEASURE_STATUS = {
  geplant: 'Geplant',
  aktiv: 'Aktiv',
  beendet: 'Beendet',
};

export const ENROLLMENT_STATUS = {
  aktiv: 'Aktiv',
  beendet: 'Beendet',
  abgebrochen: 'Abgebrochen',
};

/** ISO-Datum (YYYY-MM-DD…) -> TT.MM.JJJJ */
export function formatDate(value) {
  if (!value) return '–';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value));
  return m ? `${m[3]}.${m[2]}.${m[1]}` : String(value);
}

export function formatDateTime(value) {
  if (!value) return '–';
  const d = new Date(String(value).endsWith('Z') ? value : `${value}Z`);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString('de-DE', { dateStyle: 'medium', timeStyle: 'short' });
}

/** Alter in Jahren aus ISO-Geburtsdatum */
export function age(birthDate, today = new Date()) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(birthDate || '');
  if (!m) return null;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  let years = today.getFullYear() - y;
  if (today.getMonth() + 1 < mo || (today.getMonth() + 1 === mo && today.getDate() < d)) years -= 1;
  return years;
}

/** Label einer Auswahloption aus der Feldkonfiguration */
export function optionLabel(field, value) {
  if (value === undefined || value === null || value === '') return '';
  const options = field?.options || [];
  const find = (v) => {
    const o = options.find((opt) => (typeof opt === 'object' ? opt.value : opt) === v);
    return o ? (typeof o === 'object' ? o.label : o) : v;
  };
  if (Array.isArray(value)) return value.map(find).join(', ');
  if (typeof value === 'boolean') return value ? 'ja' : 'nein';
  return String(find(value));
}
