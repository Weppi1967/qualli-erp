import { describe, expect, it } from 'vitest';
import { age, formatDate, optionLabel } from './format';
import { errorMessage, fieldErrors } from '../api/client';

describe('formatDate', () => {
  it('formatiert ISO-Datum deutsch', () => {
    expect(formatDate('2026-01-15')).toBe('15.01.2026');
    expect(formatDate('2026-01-15T10:00:00')).toBe('15.01.2026');
  });
  it('zeigt Strich bei leerem Wert', () => {
    expect(formatDate(null)).toBe('–');
  });
});

describe('age', () => {
  it('berechnet das Alter vor und nach dem Geburtstag', () => {
    expect(age('1990-06-15', new Date(2026, 5, 14))).toBe(35);
    expect(age('1990-06-15', new Date(2026, 5, 15))).toBe(36);
    expect(age('')).toBeNull();
  });
});

describe('optionLabel', () => {
  const field = { options: [{ value: 'm', label: 'männlich' }, { value: 'w', label: 'weiblich' }] };
  it('liefert Labels für Einzel- und Mehrfachauswahl', () => {
    expect(optionLabel(field, 'm')).toBe('männlich');
    expect(optionLabel(field, ['m', 'w'])).toBe('männlich, weiblich');
    expect(optionLabel(field, 'x')).toBe('x');
    expect(optionLabel({}, true)).toBe('ja');
  });
});

describe('API-Fehlertexte', () => {
  it('nimmt die Meldung des Backends', () => {
    expect(errorMessage({ response: { status: 409, data: { error: 'Dublette' } } })).toBe('Dublette');
  });
  it('erkennt fehlende Verbindung', () => {
    expect(errorMessage({ request: {} })).toMatch(/Keine Verbindung/);
  });
  it('liefert Feldfehler', () => {
    const err = { response: { data: { details: { 'basic_info.last_name': 'Pflichtfeld' } } } };
    expect(fieldErrors(err)).toEqual({ 'basic_info.last_name': 'Pflichtfeld' });
    expect(fieldErrors({ response: { data: { details: { duplicates: [] } } } })).toEqual({ duplicates: [] });
  });
});
