"""Authentifizierung & standortbasierte Zugriffskontrolle.

Rollen:
  admin             – sieht und verwaltet alle Standorte
  location_manager  – sieht ihre zugewiesenen Standorte (Haupt- + Zusatzstandorte)
  employee          – sieht nur den eigenen Standort
"""
from functools import wraps

from flask import g, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from extensions import db
from models import Location, User
from utils.helpers import ApiError, error_response


def current_user() -> User:
    return g.current_user


def _load_user():
    verify_jwt_in_request()
    identity = get_jwt_identity()
    try:
        user = db.session.get(User, int(identity))
    except (TypeError, ValueError):
        user = None
    if user is None or not user.is_active:
        return None
    g.current_user = user
    return user


def token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if _load_user() is None:
            return error_response("Benutzer nicht gefunden oder deaktiviert.", 401)
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = _load_user()
        if user is None:
            return error_response("Benutzer nicht gefunden oder deaktiviert.", 401)
        if not user.is_admin:
            return error_response("Nur für Administratoren.", 403)
        return fn(*args, **kwargs)

    return wrapper


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = _load_user()
            if user is None:
                return error_response("Benutzer nicht gefunden oder deaktiviert.", 401)
            if user.role not in roles:
                return error_response("Keine Berechtigung für diese Aktion.", 403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def location_required(fn):
    """Wie token_required, prüft zusätzlich eine übergebene location_id
    (URL-Parameter, Query-String oder JSON-Body) gegen die erlaubten Standorte."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = _load_user()
        if user is None:
            return error_response("Benutzer nicht gefunden oder deaktiviert.", 401)
        if not user.is_admin and not user.assigned_location_ids():
            return error_response("Ihrem Konto ist kein Standort zugeordnet.", 403)
        location_id = kwargs.get("location_id") or request.args.get("location_id")
        if location_id is None and request.is_json:
            body = request.get_json(silent=True) or {}
            if isinstance(body, dict):
                location_id = body.get("location_id")
        if location_id not in (None, ""):
            try:
                location_id = int(location_id)
            except (TypeError, ValueError):
                return error_response("location_id muss eine Zahl sein.", 400)
            if not can_access_location(user, location_id):
                return error_response("Kein Zugriff auf diesen Standort.", 403)
        return fn(*args, **kwargs)

    return wrapper


def allowed_location_ids(user: User) -> list[int]:
    if user.is_admin:
        return [lid for (lid,) in db.session.query(Location.id).all()]
    return sorted(user.assigned_location_ids())


def can_access_location(user: User, location_id) -> bool:
    if location_id is None:
        return False
    if user.is_admin:
        return db.session.get(Location, int(location_id)) is not None
    return int(location_id) in user.assigned_location_ids()


def ensure_location_access(user: User, location_id):
    if not can_access_location(user, location_id):
        raise ApiError("Kein Zugriff auf diesen Standort.", 403)


def scope_query(query, column, user: User):
    """Beschränkt eine Query auf die Standorte des Benutzers und wendet
    optional den Filter ?location_id=… an."""
    requested = request.args.get("location_id")
    if requested not in (None, ""):
        try:
            requested = int(requested)
        except ValueError:
            raise ApiError("location_id muss eine Zahl sein.", 400)
        ensure_location_access(user, requested)
        return query.filter(column == requested)
    if user.is_admin:
        return query
    return query.filter(column.in_(allowed_location_ids(user) or [-1]))
