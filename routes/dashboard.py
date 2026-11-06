from datetime import date, timedelta

from flask import Blueprint, jsonify

from extensions import db
from models import Enrollment, Location, Measure, Participant
from models.base import utcnow
from utils.auth import allowed_location_ids, current_user, token_required

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


def _location_filter(user):
    return allowed_location_ids(user)


@bp.get("/stats")
@token_required
def stats():
    user = current_user()
    loc_ids = _location_filter(user) or [-1]

    participants = Participant.query.filter(Participant.is_deleted.is_(False), Participant.location_id.in_(loc_ids))
    measures = Measure.query.filter(Measure.is_deleted.is_(False), Measure.location_id.in_(loc_ids))
    enrollments = Enrollment.query.join(Measure).join(Participant).filter(
        Enrollment.is_deleted.is_(False),
        Participant.is_deleted.is_(False),
        Measure.is_deleted.is_(False),
        Measure.location_id.in_(loc_ids),
    )

    since = utcnow() - timedelta(days=30)
    today = date.today()
    measure_status = dict(
        measures.with_entities(Measure.status, db.func.count(Measure.id)).group_by(Measure.status).all()
    )
    enrollment_status = dict(
        enrollments.with_entities(Enrollment.status, db.func.count(Enrollment.id)).group_by(Enrollment.status).all()
    )
    ending_soon = (
        measures.filter(Measure.status == "aktiv", Measure.end_date >= today, Measure.end_date <= today + timedelta(days=30))
        .order_by(Measure.end_date)
        .limit(5)
        .all()
    )
    recent = participants.order_by(Participant.created_at.desc()).limit(5).all()

    return jsonify(
        participants_total=participants.count(),
        participants_new_30d=participants.filter(Participant.created_at >= since).count(),
        participants_in_active_measure=enrollments.filter(Enrollment.status == "aktiv")
        .with_entities(Enrollment.participant_id)
        .distinct()
        .count(),
        measures_total=sum(measure_status.values()),
        measures_by_status={s: measure_status.get(s, 0) for s in ("geplant", "aktiv", "beendet")},
        enrollments_total=sum(enrollment_status.values()),
        enrollments_by_status={s: enrollment_status.get(s, 0) for s in ("aktiv", "beendet", "abgebrochen")},
        locations=len(loc_ids) if loc_ids != [-1] else 0,
        measures_ending_soon=[m.to_dict() for m in ending_soon],
        recent_participants=[{"id": p.id, "display_name": p.display_name, "location_name": p.location.name, "created_at": p.created_at.isoformat()} for p in recent],
    )


@bp.get("/locations")
@token_required
def locations():
    user = current_user()
    loc_ids = _location_filter(user) or [-1]
    locs = Location.query.filter(Location.id.in_(loc_ids)).order_by(Location.name).all()

    def count_by(query, column):
        return dict(query.with_entities(column, db.func.count()).group_by(column).all())

    p_counts = count_by(Participant.query.filter(Participant.is_deleted.is_(False)), Participant.location_id)
    m_active = count_by(Measure.query.filter(Measure.is_deleted.is_(False), Measure.status == "aktiv"), Measure.location_id)
    m_total = count_by(Measure.query.filter(Measure.is_deleted.is_(False)), Measure.location_id)
    e_active = count_by(
        Enrollment.query.join(Measure).join(Participant).filter(
            Enrollment.is_deleted.is_(False), Participant.is_deleted.is_(False), Measure.is_deleted.is_(False), Enrollment.status == "aktiv"
        ),
        Measure.location_id,
    )
    return jsonify(items=[
        {
            **l.to_dict(),
            "participants": p_counts.get(l.id, 0),
            "measures_total": m_total.get(l.id, 0),
            "measures_active": m_active.get(l.id, 0),
            "enrollments_active": e_active.get(l.id, 0),
        }
        for l in locs
    ])
