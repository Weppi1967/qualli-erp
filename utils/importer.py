"""CSV/XLSX-Import (Qualli.life-Export und allgemeiner Batch-Import).

Spaltennamen werden tolerant normalisiert und über die 'aliases' aus
config/participant_fields.json den JSON-Feldern zugeordnet. Unbekannte
Spalten landen in custom_fields, damit keine Daten verloren gehen.
"""
import csv
import io

from flask import current_app

from extensions import db
from models import Location
from utils.auth import can_access_location
from utils.helpers import ApiError
from utils.participant_service import create_participant, find_duplicates, name_key
from utils.validators import load_field_config, normalize_key, validate_participant

LOCATION_ALIASES = {"standort", "location", "niederlassung", "filiale"}
IGNORED_COLUMNS = {"id", "nr", "lfd nr", ""}


def build_alias_map():
    mapping = {}
    for section in load_field_config()["sections"]:
        for field in section["fields"]:
            keys = [field["name"], field.get("label", "")] + field.get("aliases", [])
            for key in keys:
                norm = normalize_key(key)
                if norm and norm not in mapping:
                    mapping[norm] = (section["storage"], field["name"])
    return mapping


def map_columns(headers):
    alias_map = build_alias_map()
    mapped, unmapped, used = {}, [], set()
    for header in headers:
        norm = normalize_key(header)
        if norm in LOCATION_ALIASES:
            mapped[header] = ("location", None)
        elif norm in alias_map and alias_map[norm] not in used:
            mapped[header] = alias_map[norm]
            used.add(alias_map[norm])
        elif norm in IGNORED_COLUMNS:
            continue
        else:
            unmapped.append(header)
    return mapped, unmapped


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ApiError("Datei-Kodierung nicht erkannt.", 400)


def read_upload(file_storage):
    """Liest eine hochgeladene CSV- oder XLSX-Datei -> Liste von Dicts."""
    filename = (file_storage.filename or "").lower()
    raw = file_storage.read()
    if not raw:
        raise ApiError("Die Datei ist leer.", 400)
    if filename.endswith((".xlsx", ".xlsm")):
        return _read_xlsx(raw)
    if filename.endswith(".xls"):
        raise ApiError("Altes .xls-Format wird nicht unterstützt – bitte als .xlsx oder .csv speichern.", 400)
    return read_csv_text(_decode(raw))


def read_csv_text(text: str):
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        class dialect(csv.excel):
            delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = [row for row in reader if any((v or "").strip() for v in row.values() if isinstance(v, str))]
    return reader.fieldnames or [], rows


def _read_xlsx(raw: bytes):
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    try:
        headers = [str(h).strip() if h is not None else "" for h in next(rows_iter)]
    except StopIteration:
        raise ApiError("Die Tabelle ist leer.", 400)
    rows = []
    for values in rows_iter:
        if values is None or all(v in (None, "") for v in values):
            continue
        rows.append({h: ("" if v is None else v) for h, v in zip(headers, values)})
    wb.close()
    return headers, rows


def import_rows(headers, rows, user, default_location_id=None, dry_run=False, skip_duplicates=True, action="import"):
    max_rows = current_app.config["IMPORT_MAX_ROWS"]
    if len(rows) > max_rows:
        raise ApiError(f"Maximal {max_rows} Zeilen pro Import erlaubt (Datei enthält {len(rows)}).", 400)

    mapped, unmapped = map_columns(headers)
    if not any(v == ("basic_info", "last_name") for v in mapped.values()):
        raise ApiError(
            "Spalte für den Nachnamen nicht gefunden.",
            400,
            {"columns": headers, "mapped": {k: ".".join(filter(None, v)) for k, v in mapped.items()}},
        )

    locations_by_name = {normalize_key(l.name): l.id for l in Location.query.all()}
    seen_in_file = set()
    created, duplicates, errors, warnings, preview = [], [], [], [], []

    for index, row in enumerate(rows, start=2):  # Zeile 1 = Kopfzeile
        payload = {"basic_info": {}, "address_info": {}, "characteristics": {}, "custom_fields": {}}
        location_id = default_location_id
        for header, value in row.items():
            if header is None:
                continue
            target = mapped.get(header)
            if target is None:
                if header in unmapped and value not in (None, ""):
                    payload["custom_fields"][f"import_{normalize_key(header).replace(' ', '_')}"] = str(value).strip()
                continue
            storage, field = target
            if storage == "location":
                if value not in (None, ""):
                    location_id = locations_by_name.get(normalize_key(value), location_id)
                continue
            payload[storage][field] = value

        if not location_id:
            errors.append({"row": index, "error": "Kein Standort angegeben/erkannt."})
            continue
        if not can_access_location(user, location_id):
            errors.append({"row": index, "error": "Kein Zugriff auf den Standort."})
            continue

        sections, field_errors = validate_participant(payload, strict_unknown=False)
        row_warnings = []
        if field_errors:
            # Ungültige optionale Werte nicht verwerfen: Rohwert in custom_fields
            # sichern, Zeile trotzdem importieren. Fehlende Pflichtfelder -> Fehler.
            fatal = False
            for key, message in field_errors.items():
                storage, _, field = key.partition(".")
                raw = payload.get(storage, {}).pop(field, None)
                if raw in (None, ""):
                    fatal = True
                    continue
                payload["custom_fields"][f"import_{field}"] = str(raw).strip()
                row_warnings.append(message)
            if fatal:
                errors.append({"row": index, "error": "; ".join(field_errors.values())})
                continue
            sections, field_errors = validate_participant(payload, strict_unknown=False)
            if field_errors:
                errors.append({"row": index, "error": "; ".join(field_errors.values())})
                continue
            warnings.append({"row": index, "warning": "; ".join(row_warnings)})

        basic = sections["basic_info"]
        key = name_key(basic.get("first_name"), basic.get("last_name"))
        dup_in_file = key in seen_in_file
        dup_in_db = find_duplicates(basic.get("first_name"), basic.get("last_name"), basic.get("birth_date"))
        seen_in_file.add(key)
        if dup_in_file or dup_in_db:
            duplicates.append({
                "row": index,
                "name": f"{basic.get('last_name')}, {basic.get('first_name')}",
                "reason": "doppelt in Datei" if dup_in_file else "bereits vorhanden",
                "existing_ids": [p.id for p in dup_in_db if can_access_location(user, p.location_id)],
            })
            if skip_duplicates:
                continue

        if dry_run:
            if len(preview) < 20:
                preview.append({"row": index, "location_id": location_id, **sections})
            created.append(index)
            continue
        participant = create_participant(user, location_id, sections, action=action)
        created.append(participant.id)

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

    return {
        "dry_run": dry_run,
        "total_rows": len(rows),
        "created": len(created),
        "created_ids": [] if dry_run else created,
        "duplicates": duplicates,
        "errors": errors,
        "warnings": warnings,
        "column_mapping": {k: ".".join(filter(None, v)) for k, v in mapped.items()},
        "unmapped_columns": unmapped,
        "preview": preview,
    }
