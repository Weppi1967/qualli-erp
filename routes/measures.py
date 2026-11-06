from flask import Blueprint, jsonify, request

from extensions import db
from models import MEASURE_STATUSES, Enrollment, Measure
from utils.auth import current_user, ensure_location_access, roles_required, scope_query, token_required
from utils.helpers import ApiError, get_json, parse_date, paginate
from utils.validators import require_choice

bp = Blueprint("measures", __name__, url_prefix="/api/measures")

MANAGE_ROLES = ("admin", "location_manager")


def get_accessible_measure(measure_id) -> Measure:
    measure = db.session.get(Measure, measure_id)
    if measure is None or measure.is_deleted:
        raise ApiError("Maßnahme nicht gefunden.", 404)
    ensure_location_access(current_user(), measure.location_id)
    return measure


def apply_payload(measure: Measure, data: dict, creating=False):
    if creating or "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise ApiError("Name der Maßnahme ist erforderlich.", 422)
        measure.name = name[:200]
    if "number" in data:
        measure.number = (data.get("number") or "").strip() or None
    if "description" in data:
        measure.description = (data.get("description") or "").strip() or None
    if "status" in data or creating:
        measure.status = require_choice(data.get("status") or "geplant", MEASURE_STATUSES, "status")
    if "start_date" in data:
        measure.start_date = parse_date(data.get("start_date"), "Startdatum")
    if "end_date" in data:
        measure.end_date = parse_date(data.get("end_date"), "Enddatum")
    if "capacity" in data:
        cap = data.get("capacity")
        if cap in (None, ""):
            measure.capacity = None
        else:
            try:
                measure.capacity = max(0, int(cap))
            except (TypeError, ValueError):
                raise ApiError("Kapazität muss eine Zahl sein.", 422)
    if measure.start_date and measure.end_date and measure.end_date < measure.start_date:
        raise ApiError("Enddatum liegt vor dem Startdatum.", 422)


@bp.get("")
@token_required
def list_measures():
    user = current_user()
    query = Measure.query.filter(Measure.is_deleted.is_(False))
    query = scope_query(query, Measure.location_id, user)
    status = request.args.get("status")
    if status:
        statuses = [s for s in status.split(",") if s in MEASURE_STATUSES]
        query = query.filter(Measure.status.in_(statuses or ["-"]))
    search = (request.args.get("search") or "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(db.or_(Measure.name.ilike(like), Measure.number.ilike(like)))
    query = query.order_by(Measure.start_date.desc().nullslast(), Measure.name.asc())
    return jsonify(paginate(query, lambda m: m.to_dict(with_counts=True)))


@bp.post("")
@roles_required(*MANAGE_ROLES)
def create():
    data = get_json()
    user = current_user()
    location_id = data.get("location_id") or user.location_id
    if not location_id:
        raise ApiError("location_id ist erforderlich.", 422)
    ensure_location_access(user, location_id)
    measure = Measure(location_id=int(location_id))
    apply_payload(measure, data, creating=True)
    db.session.add(measure)
    db.session.commit()
    return jsonify(measure.to_dict(with_counts=True)), 201


@bp.get("/<int:measure_id>")
@token_required
def get_one(measure_id):
    measure = get_accessible_measure(measure_id)
    data = measure.to_dict(with_counts=True)
    data["enrollments"] = [
        e.to_dict()
        for e in measure.enrollments.filter(Enrollment.is_deleted.is_(False)).order_by(Enrollment.enrollment_date.desc())
    ]
    return jsonify(data)


@bp.put("/<int:measure_id>")
@roles_required(*MANAGE_ROLES)
def update(measure_id):
    user = current_user()
    measure = get_accessible_measure(measure_id)
    data = get_json()
    if data.get("location_id") not in (None, "") and int(data["location_id"]) != measure.location_id:
        ensure_location_access(user, int(data["location_id"]))
        measure.location_id = int(data["location_id"])
    apply_payload(measure, data)
    db.session.commit()
    return jsonify(measure.to_dict(with_counts=True))


@bp.delete("/<int:measure_id>")
@roles_required(*MANAGE_ROLES)
def delete(measure_id):
    measure = get_accessible_measure(measure_id)
    measure.soft_delete()
    db.session.commit()
    return jsonify(message="Maßnahme gelöscht (archiviert).", id=measure.id)
