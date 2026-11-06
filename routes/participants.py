from flask import Blueprint, jsonify, request

from extensions import db
from models import Enrollment, Measure, Participant, ParticipantChange
from models.base import utcnow
from utils.auth import (
    current_user,
    ensure_location_access,
    location_required,
    scope_query,
    token_required,
)
from utils.helpers import ApiError, error_response, get_json, int_arg, paginate
from utils.importer import import_rows, read_csv_text, read_upload
from utils.participant_service import (
    create_participant,
    diff_sections,
    find_duplicates,
    log_change,
    snapshot,
)
from utils.validators import public_field_config, validate_participant

bp = Blueprint("participants", __name__, url_prefix="/api/participants")

SORTABLE = {
    "last_name": Participant.last_name,
    "first_name": Participant.first_name,
    "created_at": Participant.created_at,
    "updated_at": Participant.updated_at,
    "location": Participant.location_id,
}


def get_accessible_participant(participant_id, include_deleted=False) -> Participant:
    participant = db.session.get(Participant, participant_id)
    if participant is None or (participant.is_deleted and not include_deleted):
        raise ApiError("Teilnehmer nicht gefunden.", 404)
    ensure_location_access(current_user(), participant.location_id)
    return participant


@bp.get("")
@token_required
def list_participants():
    user = current_user()
    query = Participant.query.filter(Participant.is_deleted.is_(False))
    query = scope_query(query, Participant.location_id, user)

    search = (request.args.get("search") or request.args.get("q") or "").strip().lower()
    for term in search.split()[:5]:
        query = query.filter(Participant.search_text.contains(term))

    measure_id = int_arg("measure_id")
    if measure_id:
        query = query.join(Enrollment).filter(
            Enrollment.measure_id == measure_id, Enrollment.is_deleted.is_(False)
        )

    sort = request.args.get("sort", "last_name")
    column = SORTABLE.get(sort.lstrip("-"), Participant.last_name)
    order = column.desc() if sort.startswith("-") else column.asc()
    query = query.order_by(order, Participant.first_name.asc(), Participant.id.asc())
    return jsonify(paginate(query, lambda p: p.to_dict()))


@bp.post("")
@location_required
def create():
    data = get_json()
    user = current_user()
    location_id = data.get("location_id") or user.location_id
    if not location_id:
        raise ApiError("location_id ist erforderlich.", 400)
    ensure_location_access(user, location_id)

    sections, errors = validate_participant(data)
    if errors:
        return error_response("Validierung fehlgeschlagen.", 422, errors)

    basic = sections["basic_info"]
    duplicates = find_duplicates(basic.get("first_name"), basic.get("last_name"), basic.get("birth_date"))
    if duplicates and not data.get("force"):
        return error_response(
            "Mögliche Dublette: Eine Person mit diesem Namen existiert bereits.",
            409,
            {"duplicates": [
                {"id": p.id, "display_name": p.display_name, "location_name": p.location.name if p.location else None}
                for p in duplicates
            ], "hint": "Mit force=true trotzdem anlegen."},
        )

    participant = create_participant(user, int(location_id), sections)
    db.session.commit()
    return jsonify(participant.to_dict()), 201


@bp.get("/<int:participant_id>")
@token_required
def get_one(participant_id):
    participant = get_accessible_participant(participant_id)
    data = participant.to_dict()
    data["enrollment_count"] = participant.enrollments.filter(Enrollment.is_deleted.is_(False)).count()
    return jsonify(data)


@bp.put("/<int:participant_id>")
@token_required
def update(participant_id):
    user = current_user()
    participant = get_accessible_participant(participant_id)
    data = get_json()
    before = snapshot(participant)

    sections, errors = validate_participant(data, existing=before)
    if errors:
        return error_response("Validierung fehlgeschlagen.", 422, errors)

    changes = diff_sections(before, sections)
    new_location = data.get("location_id")
    if new_location not in (None, "") and int(new_location) != participant.location_id:
        ensure_location_access(user, int(new_location))
        changes["location_id"] = {"old": participant.location_id, "new": int(new_location)}
        participant.location_id = int(new_location)

    for section, value in sections.items():
        setattr(participant, section, value)
    participant.refresh_derived()
    if changes:
        participant.updated_at = utcnow()
        log_change(participant, user, "update", changes)
    db.session.commit()
    return jsonify(participant.to_dict())


@bp.delete("/<int:participant_id>")
@token_required
def delete(participant_id):
    user = current_user()
    participant = get_accessible_participant(participant_id)
    participant.soft_delete()
    log_change(participant, user, "delete", {"is_deleted": {"old": False, "new": True}})
    db.session.commit()
    return jsonify(message="Teilnehmer gelöscht (archiviert).", id=participant.id)


@bp.post("/<int:participant_id>/restore")
@token_required
def restore(participant_id):
    user = current_user()
    participant = get_accessible_participant(participant_id, include_deleted=True)
    if not participant.is_deleted:
        return jsonify(participant.to_dict())
    participant.is_deleted = False
    participant.deleted_at = None
    log_change(participant, user, "restore", {"is_deleted": {"old": True, "new": False}})
    db.session.commit()
    return jsonify(participant.to_dict())


@bp.get("/<int:participant_id>/history")
@token_required
def history(participant_id):
    participant = get_accessible_participant(participant_id, include_deleted=True)
    entries = (
        ParticipantChange.query.filter_by(participant_id=participant.id)
        .order_by(ParticipantChange.timestamp.desc(), ParticipantChange.id.desc())
        .all()
    )
    return jsonify(items=[e.to_dict() for e in entries])


@bp.get("/<int:participant_id>/enrollments")
@token_required
def participant_enrollments(participant_id):
    participant = get_accessible_participant(participant_id)
    items = (
        participant.enrollments.join(Measure)
        .filter(Enrollment.is_deleted.is_(False), Measure.is_deleted.is_(False))
        .order_by(Enrollment.enrollment_date.desc())
        .all()
    )
    return jsonify(items=[e.to_dict() for e in items])


@bp.get("/config/fields")
@token_required
def field_config():
    return jsonify(public_field_config())


@bp.post("/batch")
@location_required
def batch():
    """Batch-Anlage: JSON {"participants": [...], "location_id": 1} oder
    CSV-Upload (multipart, Feld 'file'). ?dry_run=1 prüft nur."""
    user = current_user()
    dry_run = request.args.get("dry_run") in ("1", "true", "yes") or request.form.get("dry_run") in ("1", "true")
    skip_duplicates = (request.args.get("skip_duplicates") or request.form.get("skip_duplicates") or "1") not in ("0", "false")

    if "file" in request.files:
        headers, rows = read_upload(request.files["file"])
        location_id = request.form.get("location_id", type=int) or user.location_id
        if location_id:
            ensure_location_access(user, location_id)
        result = import_rows(headers, rows, user, location_id, dry_run, skip_duplicates, action="batch")
        return jsonify(result), 200 if dry_run else 201

    data = get_json()
    if isinstance(data.get("csv"), str):
        headers, rows = read_csv_text(data["csv"])
        location_id = data.get("location_id") or user.location_id
        result = import_rows(headers, rows, user, location_id, dry_run, skip_duplicates, action="batch")
        return jsonify(result), 200 if dry_run else 201

    items = data.get("participants")
    if not isinstance(items, list) or not items:
        raise ApiError("'participants' (Liste) oder eine CSV-Datei erwartet.", 400)
    if len(items) > 1000:
        raise ApiError("Maximal 1000 Einträge pro Batch.", 400)

    created, errors = [], []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append({"index": index, "error": "Objekt erwartet"})
            continue
        location_id = item.get("location_id") or data.get("location_id") or user.location_id
        try:
            ensure_location_access(user, location_id)
        except ApiError as exc:
            errors.append({"index": index, "error": exc.message})
            continue
        sections, field_errors = validate_participant(item)
        if field_errors:
            errors.append({"index": index, "error": field_errors})
            continue
        if dry_run:
            created.append(index)
            continue
        created.append(create_participant(user, int(location_id), sections, action="batch").id)

    if errors and not data.get("partial", False):
        db.session.rollback()
        return error_response("Batch abgebrochen – keine Einträge gespeichert.", 422, {"errors": errors})
    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    return jsonify(created=len(created), created_ids=[] if dry_run else created, errors=errors, dry_run=dry_run), (
        200 if dry_run else 201
    )
