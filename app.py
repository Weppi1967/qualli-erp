"""Qualli-ERP – Flask Entry Point.

Start:  python app.py            -> http://127.0.0.1:5050
Tests:  pytest tests/
"""
import json
import logging
import os
import sys

from flask import Flask, jsonify, request, send_from_directory
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from config import CONFIGS, DEV_SECRET, INSTANCE_DIR
from extensions import cors, db, jwt

__version__ = "1.0.0"
log = logging.getLogger("qualli_erp")


def create_app(config_name=None):
    config_name = config_name or os.environ.get("ERP_ENV", "development")
    app = Flask(__name__, static_folder=None)
    app.config.from_object(CONFIGS[config_name])
    INSTANCE_DIR.mkdir(exist_ok=True)

    if config_name == "production" and app.config["SECRET_KEY"].startswith(DEV_SECRET):
        raise RuntimeError("ERP_SECRET_KEY und ERP_JWT_SECRET_KEY müssen in Produktion gesetzt sein.")

    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    import models  # noqa: F401  (Modelle registrieren)
    from routes import register_blueprints

    register_blueprints(app)
    _register_jwt_callbacks()
    _register_error_handlers(app)
    _register_frontend(app)
    _register_cli(app)

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", app="qualli-erp", version=__version__)

    with app.app_context():
        db.create_all()
        bootstrap(app)

    return app


def bootstrap(app):
    """Legt Standorte aus config/locations.json und den ersten Admin an."""
    from models import Location, User

    path = app.config["LOCATIONS_FILE"]
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            entries = json.load(fh).get("locations", [])
        existing = {l.name for l in Location.query.all()}
        for entry in entries:
            if entry["name"] not in existing:
                db.session.add(Location(**{k: entry.get(k) for k in ("name", "address", "zip", "city", "phone")}))
    if User.query.count() == 0:
        admin = User(
            username=app.config["BOOTSTRAP_ADMIN_USERNAME"],
            role="admin",
            full_name="Administrator",
        )
        admin.set_password(app.config["BOOTSTRAP_ADMIN_PASSWORD"])
        db.session.add(admin)
        if not app.testing:
            log.warning("Admin-Konto '%s' angelegt – Passwort bitte nach dem ersten Login ändern.", admin.username)
    db.session.commit()


def _register_jwt_callbacks():
    from models import TokenBlocklist

    @jwt.token_in_blocklist_loader
    def is_revoked(jwt_header, jwt_payload):
        return db.session.query(TokenBlocklist.id).filter_by(jti=jwt_payload["jti"]).first() is not None

    @jwt.expired_token_loader
    def expired(jwt_header, jwt_payload):
        return jsonify(error="Sitzung abgelaufen. Bitte erneut anmelden.", code="token_expired"), 401

    @jwt.invalid_token_loader
    def invalid(reason):
        return jsonify(error="Ungültiges Token.", code="token_invalid"), 401

    @jwt.unauthorized_loader
    def missing(reason):
        return jsonify(error="Anmeldung erforderlich.", code="token_missing"), 401

    @jwt.revoked_token_loader
    def revoked(jwt_header, jwt_payload):
        return jsonify(error="Token wurde widerrufen (abgemeldet).", code="token_revoked"), 401


def _register_error_handlers(app):
    from utils.helpers import ApiError

    @app.errorhandler(ApiError)
    def handle_api_error(exc):
        db.session.rollback()
        body = {"error": exc.message}
        if exc.details:
            body["details"] = exc.details
        return jsonify(body), exc.status

    @app.errorhandler(IntegrityError)
    def handle_integrity(exc):
        db.session.rollback()
        return jsonify(error="Datenbank-Konflikt (Verknüpfung oder Eindeutigkeit verletzt)."), 409

    @app.errorhandler(HTTPException)
    def handle_http(exc):
        if request.path.startswith("/api/"):
            messages = {404: "Nicht gefunden.", 405: "Methode nicht erlaubt.", 413: "Datei zu groß (max. 10 MB)."}
            return jsonify(error=messages.get(exc.code, exc.description)), exc.code
        return exc

    @app.errorhandler(Exception)
    def handle_unexpected(exc):
        db.session.rollback()
        log.exception("Unerwarteter Fehler")
        return jsonify(error="Interner Serverfehler."), 500


def _register_frontend(app):
    """Liefert die gebaute Desktop-/Web-Oberfläche aus (qualli-erp-desktop/dist)."""
    dist = app.config["FRONTEND_DIST"]

    @app.get("/")
    @app.get("/<path:path>")
    def frontend(path="index.html"):
        if path.startswith("api/"):
            return jsonify(error="Nicht gefunden."), 404
        if not (dist / "index.html").exists():
            return (
                "<h1>Qualli-ERP API läuft</h1><p>Die Oberfläche ist noch nicht gebaut: "
                "<code>cd qualli-erp-desktop &amp;&amp; npm run build</code></p>",
                200,
            )
        target = dist / path  # send_from_directory schützt vor Pfad-Traversal
        if path != "index.html" and target.is_file():
            return send_from_directory(dist, path)
        response = send_from_directory(dist, "index.html")
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if response.mimetype == "text/html":
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                "connect-src 'self'; frame-ancestors 'none'",
            )
        return response


def _register_cli(app):
    @app.cli.command("seed")
    def seed_command():
        """Beispieldaten anlegen (210 Teilnehmer, 18 Maßnahmen, 120+ Zuordnungen)."""
        from seed import seed_sample_data

        print(seed_sample_data())


if __name__ == "__main__":
    app = create_app()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    host = os.environ.get("ERP_HOST", "127.0.0.1")
    port = int(os.environ.get("ERP_PORT", "5050"))
    print(f"Qualli-ERP Backend läuft auf http://{host}:{port}", file=sys.stderr)
    app.run(host=host, port=port, debug=False, threaded=True)
