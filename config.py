"""Konfiguration für das Qualli-ERP Backend.

Werte können über Umgebungsvariablen überschrieben werden (z.B. in einer
.env-Datei, die von start.cmd geladen wird). Für den Server-Betrieb müssen
mindestens ERP_SECRET_KEY, ERP_JWT_SECRET_KEY und ERP_DATABASE_URL gesetzt
werden.
"""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
CONFIG_DIR = BASE_DIR / "config"
FRONTEND_DIST = BASE_DIR / "qualli-erp-desktop" / "dist"

DEV_SECRET = "dev-only-bitte-in-produktion-aendern"


def _origins(value: str) -> list[str]:
    return [o.strip() for o in value.split(",") if o.strip()]


class Config:
    SECRET_KEY = os.environ.get("ERP_SECRET_KEY", DEV_SECRET)
    JWT_SECRET_KEY = os.environ.get("ERP_JWT_SECRET_KEY", DEV_SECRET + "-jwt")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "ERP_DATABASE_URL", f"sqlite:///{(INSTANCE_DIR / 'qualli_erp.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Access-Token kurzlebig, Refresh-Token 30 Tage ("30 Tage angemeldet bleiben").
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.environ.get("ERP_ACCESS_HOURS", "12")))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.environ.get("ERP_REFRESH_DAYS", "30")))
    JWT_TOKEN_LOCATION = ["headers"]

    # Vite-Dev-Server der Desktop-App. Im Normalbetrieb liefert Flask die App
    # selbst aus (gleiche Origin), CORS ist dann nicht nötig.
    CORS_ORIGINS = _origins(
        os.environ.get("ERP_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    )

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB Upload-Limit
    IMPORT_MAX_ROWS = 1000
    DEFAULT_PER_PAGE = 25
    MAX_PER_PAGE = 200

    # Bootstrap-Admin, wird nur angelegt wenn noch kein Benutzer existiert.
    BOOTSTRAP_ADMIN_USERNAME = os.environ.get("ERP_ADMIN_USERNAME", "admin")
    BOOTSTRAP_ADMIN_PASSWORD = os.environ.get("ERP_ADMIN_PASSWORD", "password123")

    PARTICIPANT_FIELDS_FILE = CONFIG_DIR / "participant_fields.json"
    LOCATIONS_FILE = CONFIG_DIR / "locations.json"
    FRONTEND_DIST = FRONTEND_DIST


class DevelopmentConfig(Config):
    DEBUG = False  # Reloader würde von Electron gestartete Prozesse verdoppeln


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET_KEY = "test-secret-key-mit-ausreichender-laenge-123"
    SECRET_KEY = "test-secret-key"
    BOOTSTRAP_ADMIN_PASSWORD = "password123"


class ProductionConfig(Config):
    pass


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
