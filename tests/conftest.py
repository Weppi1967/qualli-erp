import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402
from models import Location, User  # noqa: E402


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username="admin", password="password123"):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.get_json()
    return res.get_json()


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(client):
    return auth_header(login(client)["access_token"])


@pytest.fixture()
def locations(app):
    return Location.query.order_by(Location.id).all()


@pytest.fixture()
def make_user(app):
    def _make(username, role, location=None, extra=()):
        user = User(username=username, role=role, location_id=location.id if location else None)
        user.set_password("geheim12345")
        user.extra_locations = list(extra)
        db.session.add(user)
        db.session.commit()
        return user

    return _make


@pytest.fixture()
def user_headers(client, make_user):
    def _headers(username, role, location=None, extra=()):
        make_user(username, role, location, extra)
        return auth_header(login(client, username, "geheim12345")["access_token"])

    return _headers


def participant_payload(first="Max", last="Mustermann", location_id=1, **extra):
    payload = {
        "location_id": location_id,
        "basic_info": {"first_name": first, "last_name": last, "birth_date": "01.02.1990", "gender": "männlich"},
        "address_info": {"street": "Hauptstraße 1", "zip": "32423", "city": "Minden"},
        "characteristics": {"driving_license": "B, BE", "children": "2"},
    }
    payload.update(extra)
    return payload
