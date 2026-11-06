"""Standorte, Benutzer und Mitarbeitende."""
from flask import Blueprint, jsonify

from extensions import db
from models import ROLES, Employee, Location, User
from utils.auth import admin_required, allowed_location_ids, current_user, ensure_location_access, roles_required, scope_query, token_required
from utils.helpers import ApiError, get_json, paginate, parse_date
from utils.validators import require_choice

bp = Blueprint("admin", __name__, url_prefix="/api")


# ---------- Standorte ----------

@bp.get("/locations")
@token_required
def list_locations():
    ids = allowed_location_ids(current_user()) or [-1]
    locs = Location.query.filter(Location.id.in_(ids)).order_by(Location.name).all()
    return jsonify(items=[l.to_dict() for l in locs])


@bp.post("/locations")
@admin_required
def create_location():
    data = get_json()
    name = (data.get("name") or "").strip()
    if not name:
        raise ApiError("Name ist erforderlich.", 422)
    if Location.query.filter(db.func.lower(Location.name) == name.lower()).first():
        raise ApiError("Ein Standort mit diesem Namen existiert bereits.", 409)
    loc = Location(name=name)
    _apply_location(loc, data)
    db.session.add(loc)
    db.session.commit()
    return jsonify(loc.to_dict()), 201


@bp.put("/locations/<int:location_id>")
@admin_required
def update_location(location_id):
    loc = db.session.get(Location, location_id) or _not_found("Standort")
    data = get_json()
    if data.get("name"):
        loc.name = data["name"].strip()
    _apply_location(loc, data)
    db.session.commit()
    return jsonify(loc.to_dict())


def _apply_location(loc, data):
    for key in ("address", "zip", "city", "phone"):
        if key in data:
            setattr(loc, key, (data.get(key) or "").strip() or None)
    if "is_active" in data:
        loc.is_active = bool(data["is_active"])


def _not_found(what):
    raise ApiError(f"{what} nicht gefunden.", 404)


# ---------- Benutzer (nur Admin) ----------

@bp.get("/users")
@admin_required
def list_users():
    query = User.query.order_by(User.username)
    return jsonify(paginate(query, lambda u: u.to_dict()))


def _apply_user(user: User, data: dict, creating=False):
    if creating or "role" in data:
        user.role = require_choice(data.get("role") or "employee", ROLES, "role")
    for key in ("email", "full_name"):
        if key in data:
            setattr(user, key, (data.get(key) or "").strip() or None)
    if "location_id" in data:
        lid = data.get("location_id")
        if lid not in (None, "") and db.session.get(Location, int(lid)) is None:
            raise ApiError("Standort nicht gefunden.", 422)
        user.location_id = int(lid) if lid not in (None, "") else None
    if "location_ids" in data:
        ids = [int(i) for i in (data.get("location_ids") or [])]
        user.extra_locations = Location.query.filter(Location.id.in_(ids)).all() if ids else []
    if "is_active" in data:
        user.is_active = bool(data["is_active"])
    if data.get("password"):
        if len(data["password"]) < 8:
            raise ApiError("Passwort muss mindestens 8 Zeichen haben.", 422)
        user.set_password(data["password"])
    if user.role != "admin" and not user.location_id and not user.extra_locations:
        raise ApiError("Nicht-Admins brauchen mindestens einen Standort.", 422)


@bp.post("/users")
@admin_required
def create_user():
    data = get_json()
    username = (data.get("username") or "").strip()
    if not username or not data.get("password"):
        raise ApiError("Benutzername und Passwort sind erforderlich.", 422)
    if User.query.filter(db.func.lower(User.username) == username.lower()).first():
        raise ApiError("Benutzername ist bereits vergeben.", 409)
    user = User(username=username)
    _apply_user(user, data, creating=True)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@bp.put("/users/<int:user_id>")
@admin_required
def update_user(user_id):
    user = db.session.get(User, user_id) or _not_found("Benutzer")
    data = get_json()
    if user.id == current_user().id and (data.get("is_active") is False or data.get("role", "admin") != "admin"):
        raise ApiError("Eigenes Admin-Konto kann nicht deaktiviert oder herabgestuft werden.", 422)
    _apply_user(user, data)
    db.session.commit()
    return jsonify(user.to_dict())


# ---------- Mitarbeitende ----------

@bp.get("/employees")
@token_required
def list_employees():
    query = Employee.query.filter(Employee.is_deleted.is_(False))
    query = scope_query(query, Employee.location_id, current_user()).order_by(Employee.name)
    return jsonify(paginate(query, lambda e: e.to_dict()))


def _apply_employee(emp: Employee, data: dict, creating=False):
    if creating or "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise ApiError("Name ist erforderlich.", 422)
        emp.name = name
    for key in ("role", "email", "phone"):
        if key in data:
            setattr(emp, key, (data.get(key) or "").strip() or None)
    if "start_date" in data:
        emp.start_date = parse_date(data.get("start_date"), "Eintrittsdatum")


@bp.post("/employees")
@roles_required("admin", "location_manager")
def create_employee():
    data = get_json()
    location_id = data.get("location_id") or current_user().location_id
    ensure_location_access(current_user(), location_id)
    emp = Employee(location_id=int(location_id))
    _apply_employee(emp, data, creating=True)
    db.session.add(emp)
    db.session.commit()
    return jsonify(emp.to_dict()), 201


@bp.put("/employees/<int:employee_id>")
@roles_required("admin", "location_manager")
def update_employee(employee_id):
    emp = db.session.get(Employee, employee_id)
    if emp is None or emp.is_deleted:
        _not_found("Mitarbeiter:in")
    ensure_location_access(current_user(), emp.location_id)
    data = get_json()
    if data.get("location_id") not in (None, ""):
        ensure_location_access(current_user(), data["location_id"])
        emp.location_id = int(data["location_id"])
    _apply_employee(emp, data)
    db.session.commit()
    return jsonify(emp.to_dict())


@bp.delete("/employees/<int:employee_id>")
@roles_required("admin", "location_manager")
def delete_employee(employee_id):
    emp = db.session.get(Employee, employee_id)
    if emp is None or emp.is_deleted:
        _not_found("Mitarbeiter:in")
    ensure_location_access(current_user(), emp.location_id)
    emp.soft_delete()
    db.session.commit()
    return jsonify(message="Mitarbeiter:in archiviert.", id=emp.id)
