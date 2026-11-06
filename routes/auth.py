from datetime import datetime, timezone

from flask import Blueprint, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)

from extensions import db
from models import Location, TokenBlocklist, User
from models.base import utcnow
from utils.auth import current_user, token_required
from utils.helpers import ApiError, error_response, get_json

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _claims(user: User):
    return {"role": user.role, "username": user.username}


def _block(token_payload):
    exp = token_payload.get("exp")
    db.session.add(
        TokenBlocklist(
            jti=token_payload["jti"],
            token_type=token_payload.get("type", "access"),
            user_id=int(token_payload["sub"]) if token_payload.get("sub") else None,
            expires_at=datetime.fromtimestamp(exp, tz=timezone.utc).replace(tzinfo=None) if exp else None,
        )
    )


@bp.post("/login")
def login():
    data = get_json()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return error_response("Benutzername und Passwort erforderlich.", 400)
    user = User.query.filter(db.func.lower(User.username) == username.lower()).first()
    if user is None or not user.check_password(password):
        return error_response("Benutzername oder Passwort falsch.", 401)
    if not user.is_active:
        return error_response("Dieses Konto ist deaktiviert.", 403)
    user.last_login_at = utcnow()
    db.session.commit()
    identity = str(user.id)
    return jsonify(
        access_token=create_access_token(identity=identity, additional_claims=_claims(user)),
        refresh_token=create_refresh_token(identity=identity),
        token_type="Bearer",
        user=user.to_dict(),
    )


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None or not user.is_active:
        return error_response("Benutzer nicht gefunden oder deaktiviert.", 401)
    return jsonify(
        access_token=create_access_token(identity=str(user.id), additional_claims=_claims(user)),
        token_type="Bearer",
    )


@bp.post("/logout")
@token_required
def logout():
    """Widerruft das Access-Token und (falls mitgeschickt) das Refresh-Token."""
    _block(get_jwt())
    refresh_token = get_json().get("refresh_token")
    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            if payload.get("sub") == get_jwt_identity():
                _block(payload)
        except Exception:  # abgelaufen/ungültig: nichts zu widerrufen
            pass
    db.session.commit()
    return jsonify(message="Abgemeldet.")


@bp.get("/me")
@token_required
def me():
    user = current_user()
    if user.is_admin:
        locations = Location.query.order_by(Location.name).all()
    else:
        ids = user.assigned_location_ids()
        locations = Location.query.filter(Location.id.in_(ids)).order_by(Location.name).all()
    return jsonify(user=user.to_dict(), locations=[l.to_dict() for l in locations])


@bp.post("/change-password")
@token_required
def change_password():
    data = get_json()
    user = current_user()
    if not user.check_password(data.get("current_password") or ""):
        raise ApiError("Aktuelles Passwort ist falsch.", 400)
    new = data.get("new_password") or ""
    if len(new) < 8:
        raise ApiError("Das neue Passwort muss mindestens 8 Zeichen haben.", 400)
    user.set_password(new)
    db.session.commit()
    return jsonify(message="Passwort geändert.")
