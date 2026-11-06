"""Import aus Qualli.life (Modulname nicht 'import.py', da 'import' ein Python-Schlüsselwort ist)."""
from flask import Blueprint, jsonify, request

from utils.auth import current_user, ensure_location_access, token_required
from utils.helpers import ApiError
from utils.importer import build_alias_map, import_rows, read_upload

bp = Blueprint("import", __name__, url_prefix="/api/import")


@bp.post("/qualli-life")
@token_required
def qualli_life():
    """Multipart-Upload: file=<csv|xlsx>, location_id=<Standard-Standort>,
    dry_run=1 (nur prüfen), skip_duplicates=0 (Dubletten trotzdem anlegen).
    Eine Spalte 'Standort' in der Datei hat Vorrang vor location_id."""
    user = current_user()
    upload = request.files.get("file")
    if upload is None:
        raise ApiError("Bitte eine Datei im Feld 'file' hochladen.", 400)
    location_id = request.form.get("location_id", type=int) or user.location_id
    if location_id:
        ensure_location_access(user, location_id)
    dry_run = (request.form.get("dry_run") or request.args.get("dry_run") or "0") in ("1", "true", "yes")
    skip_duplicates = (request.form.get("skip_duplicates") or "1") not in ("0", "false")
    headers, rows = read_upload(upload)
    result = import_rows(headers, rows, user, location_id, dry_run, skip_duplicates, action="import")
    return jsonify(result), 200 if dry_run else 201


@bp.get("/qualli-life/mapping")
@token_required
def mapping():
    """Zeigt, welche Spaltennamen automatisch erkannt werden."""
    alias_map = build_alias_map()
    return jsonify(columns={k: ".".join(v) for k, v in sorted(alias_map.items())})
