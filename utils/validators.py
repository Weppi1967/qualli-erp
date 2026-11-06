"""Validierung der flexiblen Teilnehmerdaten anhand von config/participant_fields.json."""
import json
import re
import unicodedata
from datetime import date

from flask import current_app

from utils.helpers import ApiError, parse_date

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TRUE = {"true", "1", "ja", "j", "yes", "y", "x", "vorhanden"}
_FALSE = {"false", "0", "nein", "n", "no", ""}

_cache = {"mtime": None, "config": None}


def load_field_config():
    path = current_app.config["PARTICIPANT_FIELDS_FILE"]
    mtime = path.stat().st_mtime
    if _cache["mtime"] != mtime:
        with open(path, encoding="utf-8") as fh:
            config = json.load(fh)
        config.pop("_hinweis", None)
        _cache.update(mtime=mtime, config=config)
    return _cache["config"]


def public_field_config():
    """Formular-Konfiguration ohne interne Import-Aliase."""
    config = load_field_config()
    sections = []
    for section in config["sections"]:
        fields = [{k: v for k, v in f.items() if k != "aliases"} for f in section["fields"]]
        sections.append({**{k: v for k, v in section.items() if k != "fields"}, "fields": fields})
    return {"sections": sections}


def sections_by_storage():
    return {s["storage"]: s for s in load_field_config()["sections"]}


def normalize_key(text) -> str:
    """'Straße/Hausnr.' -> 'strasse hausnr' – für tolerantes Spalten-Matching."""
    text = str(text or "").strip().lower()
    text = text.replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def _option_values(field):
    return [o["value"] if isinstance(o, dict) else o for o in field.get("options", [])]


def _match_option(field, raw):
    """Akzeptiert Wert oder Label (unabhängig von Groß-/Kleinschreibung)."""
    needle = normalize_key(raw)
    for opt in field.get("options", []):
        value = opt["value"] if isinstance(opt, dict) else opt
        label = opt.get("label", value) if isinstance(opt, dict) else opt
        if needle in (normalize_key(value), normalize_key(label)):
            return value
    return None


def _clean_value(field, raw):
    """Gibt (wert, fehler) zurück. Leere Werte -> (None, None)."""
    ftype = field.get("type", "text")
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None, None
    if ftype in ("text", "textarea", "tel"):
        value = str(raw).strip()
        max_len = field.get("max_length", 5000 if ftype == "textarea" else 300)
        if len(value) > max_len:
            return None, f"maximal {max_len} Zeichen"
        if field.get("pattern") and not re.match(field["pattern"], value):
            return None, "ungültiges Format"
        return value, None
    if ftype == "email":
        value = str(raw).strip()
        if not _EMAIL.match(value):
            return None, "ungültige E-Mail-Adresse"
        return value, None
    if ftype == "date":
        try:
            parsed = parse_date(raw, field.get("label", field["name"]))
        except ApiError as exc:
            return None, exc.message
        if parsed.year > date.today().year + 50 or parsed.year < 1900:
            return None, "Datum außerhalb des gültigen Bereichs"
        return parsed.isoformat(), None
    if ftype == "number":
        try:
            text = str(raw).strip().replace(",", ".")
            value = float(text)
            value = int(value) if value.is_integer() else value
        except ValueError:
            return None, "muss eine Zahl sein"
        if "min" in field and value < field["min"]:
            return None, f"muss mindestens {field['min']} sein"
        if "max" in field and value > field["max"]:
            return None, f"darf höchstens {field['max']} sein"
        return value, None
    if ftype == "boolean":
        if isinstance(raw, bool):
            return raw, None
        text = normalize_key(raw)
        if text in _TRUE:
            return True, None
        if text in _FALSE:
            return False, None
        return None, "ja/nein erwartet"
    if ftype == "select":
        value = _match_option(field, raw)
        if value is None:
            return None, f"ungültige Auswahl '{raw}'"
        return value, None
    if ftype == "multiselect":
        items = raw if isinstance(raw, list) else re.split(r"[,;/]+", str(raw))
        values, invalid = [], []
        for item in items:
            if str(item).strip() == "":
                continue
            matched = _match_option(field, item)
            if matched is None:
                invalid.append(str(item).strip())
            elif matched not in values:
                values.append(matched)
        if invalid:
            return None, "ungültige Auswahl: " + ", ".join(invalid)
        return values or None, None
    return str(raw).strip(), None


def validate_participant(payload: dict, existing=None, strict_unknown=True):
    """Validiert und normalisiert die JSON-Sektionen eines Teilnehmers.

    payload:  {"basic_info": {...}, "address_info": {...}, "characteristics": {...}, "custom_fields": {...}}
    existing: bestehende Sektionen (bei PUT) – gelieferte Felder überschreiben,
              leere Werte entfernen ein Feld.
    Rückgabe: (sektionen_dict, fehler_dict)
    """
    existing = existing or {}
    sections = sections_by_storage()
    result, errors = {}, {}

    for storage, section in sections.items():
        merged = dict(existing.get(storage) or {})
        incoming = payload.get(storage)
        if incoming is not None and not isinstance(incoming, dict):
            errors[storage] = "Objekt erwartet"
            continue
        fields = {f["name"]: f for f in section["fields"]}
        for key, raw in (incoming or {}).items():
            field = fields.get(key)
            if field is None:
                if strict_unknown:
                    errors[f"{storage}.{key}"] = "unbekanntes Feld"
                continue
            value, err = _clean_value(field, raw)
            if err:
                errors[f"{storage}.{key}"] = f"{field.get('label', key)}: {err}"
            elif value is None:
                merged.pop(key, None)
            else:
                merged[key] = value
        for name, field in fields.items():
            if field.get("required") and merged.get(name) in (None, "", []):
                errors[f"{storage}.{name}"] = f"{field.get('label', name)} ist ein Pflichtfeld"
        result[storage] = merged

    custom = payload.get("custom_fields")
    if custom is not None and not isinstance(custom, dict):
        errors["custom_fields"] = "Objekt erwartet"
    else:
        merged = dict(existing.get("custom_fields") or {})
        for key, value in (custom or {}).items():
            if value in (None, ""):
                merged.pop(key, None)
            elif isinstance(value, (str, int, float, bool, list)):
                merged[str(key)[:100]] = value
            else:
                errors[f"custom_fields.{key}"] = "nur einfache Werte erlaubt"
        result["custom_fields"] = merged

    return result, errors


def require_choice(value, choices, field):
    if value not in choices:
        raise ApiError(f"{field} muss einer der Werte {', '.join(choices)} sein.", 400)
    return value
