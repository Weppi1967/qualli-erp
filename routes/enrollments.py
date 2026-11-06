from datetime import date

from flask import Blueprint, jsonify, request

from extensions import db
from models import ENROLLMENT_STATUSES, Enrollment, Measure, Participant
from utils.auth import current_user, ensure_location_access, scope_query, token_required
from utils.helpers import ApiError, get_json, int_arg, paginate, parse_date
from utils.validators import require_choice

bp = Blueprint("enrollments", __name__, url_prefix="/api/enrollments")


def _get_enrollment(enrollment_id) -> Enrollment:
    enrollment = db.session.get(Enrollment, enrollment_id)
    if enrollment is None or enrollment.is_deleted:
        raise ApiError("Zuordnung nicht gefunden.", 404)
    ensure_location_access(current_user(), enrollment.measure.location_id)
    return enrollment


@bp.get("")
@token_required
def list_enrollments():
    user = current_user()
    query = Enrollment.query.join(Measure).join(Participant).filter(
        Enrollment.is_deleted.is_(False), Participant.is_deleted.is_(False), Measure.is_deleted.is_(False)
    )
    query = scope_query(query, Measure.location_id, user)
    participant_id = int_arg("participant_id")
    if participant_id:
        query = query.filter(Enrollment.participant_id == participant_id)
    measure_id = int_arg("measure_id")
    if measure_id:
        query = query.filter(Enrollment.measure_id == measure_id)
    status = request.args.get("status")
    if status:
        query = query.filter(Enrollment.status.in_([s for s in status.split(",") if s in ENROLLMENT_STATUSES] or ["-"]))
    query = query.order_by(Enrollment.enrollment_date.desc(), Enrollment.id.desc())
    return jsonify(paginate(query, lambda e: e.to_dict()))


@bp.post("")
@token_required
def create():
    user = current_user()
    data = get_json()
    participant = db.session.get(Participant, data.get("participant_id") or 0)
    measure = db.session.get(Measure, data.get("measure_id") or 0)
    if participant is None or participant.is_deleted:
        raise ApiError("Teilnehmer nicht gefunden.", 404)
    if measure is None or measure.is_deleted:
        raise ApiError("Maßnahme nicht gefunden.", 404)
    ensure_location_access(user, participant.location_id)
    ensure_location_access(user, measure.location_id)
    if measure.status == "beendet":
        raise ApiError("Die Maßnahme ist bereits beendet.", 422)

    existing = Enrollment.query.filter_by(
        participant_id=participant.id, measure_id=measure.id, is_deleted=False, status="aktiv"
    ).first()
    if existing:
        raise ApiError("Teilnehmer ist dieser Maßnahme bereits aktiv zugeordnet.", 409)
    if measure.capacity and measure.active_enrollment_count() >= measure.capacity and not data.get("force"):
        raise ApiError(f"Maßnahme ist voll ({measure.capacity} Plätze).", 409)

    status = require_choice(data.get("status") or "aktiv", ENROLLMENT_STATUSES, "status")
    enrollment = Enrollment(
        participant_id=participant.id,
        measure_id=measure.id,
        status=status,
        enrollment_date=parse_date(data.get("enrollment_date"), "Eintrittsdatum") or date.today(),
        exit_date=parse_date(data.get("exit_date"), "Austrittsdatum"),
        notes=(data.get("notes") or "").strip() or None,
    )
    db.session.add(enrollment)
    db.session.commit()
    return jsonify(enrollment.to_dict()), 201


@bp.get("/<int:enrollment_id>")
@token_required
def get_one(enrollment_id):
    return jsonify(_get_enrollment(enrollment_id).to_dict())


@bp.put("/<int:enrollment_id>")
@token_required
def update(enrollment_id):
    enrollment = _get_enrollment(enrollment_id)
    data = get_json()
    if "status" in data:
        enrollment.status = require_choice(data["status"], ENROLLMENT_STATUSES, "status")
        if enrollment.status != "aktiv" and not enrollment.exit_date and "exit_date" not in data:
            enrollment.exit_date = date.today()
        if enrollment.status == "aktiv" and "exit_date" not in data:
            enrollment.exit_date = None
    if "enrollment_date" in data:
        enrollment.enrollment_date = parse_date(data["enrollment_date"], "Eintrittsdatum") or enrollment.enrollment_date
    if "exit_date" in data:
        enrollment.exit_date = parse_date(data["exit_date"], "Austrittsdatum")
    if "notes" in data:
        enrollment.notes = (data.get("notes") or "").strip() or None
    if enrollment.exit_date and enrollment.exit_date < enrollment.enrollment_date:
        raise ApiError("Austrittsdatum liegt vor dem Eintrittsdatum.", 422)
    db.session.commit()
    return jsonify(enrollment.to_dict())


@bp.delete("/<int:enrollment_id>")
@token_required
def delete(enrollment_id):
    enrollment = _get_enrollment(enrollment_id)
    enrollment.soft_delete()
    db.session.commit()
    return jsonify(message="Zuordnung entfernt.", id=enrollment.id)
