# Qualli-ERP – Profilingbüro Glaser

ERP-System für den Bildungsträger (Teilnehmer, Maßnahmen, Zuordnungen, Standorte) als Ersatz für Qualli.life.
Flask-REST-API + SQLite, Desktop-App mit Electron + React.

## Schnellstart (Windows)

```
setup.cmd                          (einmalig: Python-Umgebung, Pakete, Oberfläche bauen)
.venv\Scripts\python.exe seed.py   (optional: Beispieldaten, 210 Teilnehmer / 18 Maßnahmen)
start.cmd                          (Desktop-App starten – startet das Backend automatisch)
```

Erster Login: **admin / password123** → bitte sofort unter *Einstellungen → Passwort ändern* ändern.
Beispieldaten wieder entfernen: `.venv\Scripts\python.exe seed.py --remove`

Das Backend läuft auf **http://127.0.0.1:5050** (Port 5050, damit es nicht mit dem alten MVP auf Port 5000 kollidiert;
änderbar über `ERP_PORT`). Die Oberfläche ist dort auch im Browser erreichbar.

## Entwicklung

```
.venv\Scripts\python.exe app.py              Backend
cd qualli-erp-desktop && npm run dev          Vite-Dev-Server + Electron mit Hot-Reload
.venv\Scripts\python.exe -m pytest            Backend-Tests
cd qualli-erp-desktop && npm test             Frontend-Tests
```

## Aufbau

| Pfad | Inhalt |
| --- | --- |
| `app.py` | Flask-App (Factory), Fehlerbehandlung, Auslieferung der Oberfläche, Bootstrap von Standorten/Admin |
| `config.py` | Konfiguration (Umgebungsvariablen `ERP_*`) |
| `models/` | User, Location, Participant (JSON-Felder), Measure, Enrollment, Employee, ParticipantChange (Audit), TokenBlocklist |
| `routes/` | auth, participants, measures, enrollments, dashboard, reports, import_routes, admin (Standorte/Benutzer/Mitarbeitende) |
| `utils/auth.py` | `@token_required`, `@admin_required`, `@roles_required`, `@location_required`, Standort-Filter |
| `utils/validators.py` | Validierung der Teilnehmerfelder anhand der Feldkonfiguration |
| `utils/importer.py` | CSV/XLSX-Import mit automatischer Spaltenzuordnung und Dublettenprüfung |
| `config/participant_fields.json` | **Formularfelder** – neue Felder hier ergänzen, keine DB-Migration nötig |
| `config/locations.json` | Standorte (werden beim Start angelegt) |
| `qualli-erp-desktop/` | Electron-Hauptprozess (`main.js`), React-Oberfläche (`src/`) |

## Rollen

- **admin** – alle Standorte, Benutzerverwaltung
- **location_manager** – eigene(r) Standort(e) (Haupt- + Zusatzstandorte), darf Maßnahmen verwalten
- **employee** – nur eigener Standort, Teilnehmer und Zuordnungen

## API (Auszug)

Alle Endpunkte außer Login/Health erwarten `Authorization: Bearer <access_token>`.

- Auth: `POST /api/auth/login`, `POST /api/auth/refresh` (mit Refresh-Token), `POST /api/auth/logout`, `GET /api/auth/me`, `POST /api/auth/change-password`
- Teilnehmer: `GET/POST /api/participants` (`page`, `per_page`, `search`, `location_id`, `sort`), `GET/PUT/DELETE /api/participants/<id>`, `POST /api/participants/<id>/restore`, `GET /api/participants/<id>/history`, `GET /api/participants/<id>/enrollments`, `POST /api/participants/batch`, `GET /api/participants/config/fields`
- Maßnahmen: `GET/POST /api/measures` (`status=aktiv,geplant`), `GET/PUT/DELETE /api/measures/<id>`
- Zuordnungen: `GET/POST /api/enrollments`, `GET/PUT/DELETE /api/enrollments/<id>`
- Dashboard: `GET /api/dashboard/stats`, `GET /api/dashboard/locations`
- Berichte: `GET /api/reports/participants-export` (CSV), `GET /api/reports/measures-summary[?format=csv]`, `GET /api/reports/enrollments-by-location[?format=csv]`
- Import: `POST /api/import/qualli-life` (multipart: `file`, `location_id`, `dry_run=1`), `GET /api/import/qualli-life/mapping`
- Verwaltung: `GET/POST /api/locations`, `PUT /api/locations/<id>`, `GET/POST /api/users`, `PUT /api/users/<id>`, `GET/POST /api/employees`, `PUT/DELETE /api/employees/<id>`

Löschen ist immer ein Soft-Delete (`is_deleted`); jede Teilnehmeränderung landet im Audit-Trail.

## Offene Punkte

- Standortliste prüfen: In der Vorgabe stehen „6 Standorte“, aber 7 Namen (Bad Oeynhausen ×2) – siehe `config/locations.json`.
- Echtes Qualli.life-Exportbeispiel testen und ggf. Spalten-Aliase in `participant_fields.json` ergänzen.
- Phase 3/4: PDF-Berichte, Anwesenheit, Rate-Limiting für Login, PostgreSQL/Gunicorn/Nginx für den Server-Betrieb.
