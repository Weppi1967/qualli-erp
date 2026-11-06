from datetime import date

from flask import Blueprint, jsonify, request

from extensions import db
from models import Enrollment, Location, Measure, Participant
from utils.auth import allowed_location_ids, current_user, scope_query, token_required
from utils.helpers import csv_response
from utils.validators import load_field_config

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


def _option_label(field, value):
    labels = {o["value"]: o.get("label", o["value"]) for o in field.get("options", []) if isinstance(o, dict)}
    if isinstance(value, list):
        return [labels.get(v, v) for v in value]
    return labels.get(value, value)


@bp.get("/participants-export")
@token_required
def participants_export():
    """CSV-Export aller (sichtbaren) Teilnehmer mit allen konfigurierten Feldern."""
    user = current_user()
    query = Participant.query.filter(Participant.is_deleted.is_(False))
    query = scope_query(query, Participant.location_id, user)
    query = query.order_by(Participant.last_name, Participant.first_name)

    fields = [(s["storage"], f) for s in load_field_config()["sections"] for f in s["fields"]]
    header = ["ID", "Standort"] + [f.get("label", f["name"]) for _, f in fields] + ["Angelegt am", "Geändert am"]

    def rows():
        for p in query.yield_per(200):
            row = [p.id, p.location.name if p.location else ""]
            for storage, field in fields:
                value = (getattr(p, storage) or {}).get(field["name"])
                row.append(_option_label(field, value) if value is not None else "")
            row += [p.created_at.strftime("%d.%m.%Y"), p.updated_at.strftime("%d.%m.%Y")]
            yield row

    return csv_response(f"teilnehmer_{date.today().isoformat()}.csv", header, rows())


@bp.get("/measures-summary")
@token_required
def measures_summary():
    user = current_user()
    query = Measure.query.filter(Measure.is_deleted.is_(False))
    query = scope_query(query, Measure.location_id, user)
    measures = query.order_by(Measure.status, Measure.start_date.desc().nullslast()).all()

    counts = {}
    if measures:
        rows = (
            db.session.query(Enrollment.measure_id, Enrollment.status, db.func.count())
            .join(Participant)
            .filter(
                Enrollment.is_deleted.is_(False),
                Participant.is_deleted.is_(False),
                Enrollment.measure_id.in_([m.id for m in measures]),
            )
            .group_by(Enrollment.measure_id, Enrollment.status)
            .all()
        )
        for measure_id, status, count in rows:
            counts.setdefault(measure_id, {})[status] = count

    items = []
    for m in measures:
        c = counts.get(m.id, {})
        total = sum(c.values())
        items.append({
            **m.to_dict(),
            "enrollments_total": total,
            "enrollments_active": c.get("aktiv", 0),
            "enrollments_finished": c.get("beendet", 0),
            "enrollments_cancelled": c.get("abgebrochen", 0),
            "dropout_rate": round(c.get("abgebrochen", 0) / total * 100, 1) if total else 0.0,
            "utilization": round(c.get("aktiv", 0) / m.capacity * 100, 1) if m.capacity else None,
        })

    if request.args.get("format") == "csv":
        return csv_response(
            f"massnahmen_{date.today().isoformat()}.csv",
            ["ID", "Maßnahme", "Nummer", "Standort", "Status", "Start", "Ende", "Plätze", "Zuordnungen", "Aktiv", "Beendet", "Abgebrochen", "Abbruchquote %"],
            ([i["id"], i["name"], i["number"], i["location_name"], i["status"], i["start_date"], i["end_date"], i["capacity"],
              i["enrollments_total"], i["enrollments_active"], i["enrollments_finished"], i["enrollments_cancelled"],
              str(i["dropout_rate"]).replace(".", ",")] for i in items),
        )
    return jsonify(items=items)


@bp.get("/enrollments-by-location")
@token_required
def enrollments_by_location():
    user = current_user()
    loc_ids = allowed_location_ids(user) or [-1]
    rows = (
        db.session.query(Measure.location_id, Enrollment.status, db.func.count(Enrollment.id))
        .join(Enrollment.measure)
        .join(Enrollment.participant)
        .filter(
            Enrollment.is_deleted.is_(False),
            Participant.is_deleted.is_(False),
            Measure.is_deleted.is_(False),
            Measure.location_id.in_(loc_ids),
        )
        .group_by(Measure.location_id, Enrollment.status)
        .all()
    )
    data = {}
    for location_id, status, count in rows:
        data.setdefault(location_id, {})[status] = count
    locations = Location.query.filter(Location.id.in_(loc_ids)).order_by(Location.name).all()
    items = []
    for l in locations:
        c = data.get(l.id, {})
        items.append({
            "location_id": l.id,
            "location_name": l.name,
            "aktiv": c.get("aktiv", 0),
            "beendet": c.get("beendet", 0),
            "abgebrochen": c.get("abgebrochen", 0),
            "total": sum(c.values()),
        })
    if request.args.get("format") == "csv":
        return csv_response(
            f"zuordnungen_standorte_{date.today().isoformat()}.csv",
            ["Standort", "Aktiv", "Beendet", "Abgebrochen", "Gesamt"],
            ([i["location_name"], i["aktiv"], i["beendet"], i["abgebrochen"], i["total"]] for i in items),
        )
    return jsonify(items=items)
