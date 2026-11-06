from extensions import db
from models import Enrollment, Location, Measure, Participant, User
from utils.participant_service import create_participant, diff_sections
from utils.validators import validate_participant


def test_bootstrap_creates_locations_and_admin(app):
    names = {l.name for l in Location.query.all()}
    assert {"Minden", "Lübbecke", "Espelkamp", "Petershagen"} <= names
    admin = User.query.filter_by(username="admin").one()
    assert admin.role == "admin"
    assert admin.check_password("password123")
    assert admin.password_hash != "password123"


def test_participant_derived_fields_and_timestamps(app, locations):
    p = create_participant(None, locations[0].id, {"basic_info": {"first_name": "Erika", "last_name": "Muster"}})
    db.session.commit()
    assert p.first_name == "Erika" and p.last_name == "Muster"
    assert "erika" in p.search_text
    assert p.created_at is not None and p.updated_at is not None
    assert p.is_deleted is False
    assert p.display_name == "Muster, Erika"


def test_foreign_keys_enforced(app):
    import pytest
    from sqlalchemy.exc import IntegrityError

    db.session.add(Measure(name="X", location_id=9999, status="aktiv"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_validator_normalizes_values(app):
    sections, errors = validate_participant({
        "basic_info": {"first_name": " Max ", "last_name": "M", "birth_date": "1.2.1990", "gender": "männlich"},
        "characteristics": {"driving_license": "b; CE", "children": "2", "own_vehicle": "ja"},
    })
    assert errors == {}
    assert sections["basic_info"]["first_name"] == "Max"
    assert sections["basic_info"]["birth_date"] == "1990-02-01"
    assert sections["basic_info"]["gender"] == "m"
    assert sections["characteristics"]["driving_license"] == ["B", "CE"]
    assert sections["characteristics"]["children"] == 2
    assert sections["characteristics"]["own_vehicle"] is True


def test_validator_reports_errors(app):
    _, errors = validate_participant({
        "basic_info": {"first_name": "", "email": "keine-mail", "gender": "xyz", "unbekannt": 1},
        "address_info": {"zip": "123"},
    })
    assert "basic_info.first_name" in errors
    assert "basic_info.last_name" in errors
    assert "basic_info.email" in errors
    assert "basic_info.gender" in errors
    assert "basic_info.unbekannt" in errors
    assert "address_info.zip" in errors


def test_diff_sections():
    changes = diff_sections({"basic_info": {"a": 1, "b": 2}}, {"basic_info": {"a": 1, "b": 3, "c": 4}})
    assert changes == {"basic_info": {"b": {"old": 2, "new": 3}, "c": {"old": None, "new": 4}}}


def test_enrollment_relationships(app, locations):
    p = create_participant(None, locations[0].id, {"basic_info": {"first_name": "A", "last_name": "B"}})
    m = Measure(name="Kurs", location_id=locations[0].id, status="aktiv", capacity=10)
    db.session.add(m)
    db.session.flush()
    db.session.add(Enrollment(participant_id=p.id, measure_id=m.id, status="aktiv", enrollment_date=m.created_at.date() if m.created_at else __import__("datetime").date.today()))
    db.session.commit()
    assert m.active_enrollment_count() == 1
    assert p.enrollments.count() == 1


def test_seed_sample_data(app):
    from seed import remove_sample_data, seed_sample_data

    msg = seed_sample_data()
    assert "210 Teilnehmer" in msg
    assert Participant.query.count() == 210
    assert Measure.query.count() == 18
    assert Enrollment.query.count() >= 120
    assert "bereits" in seed_sample_data()
    remove_sample_data()
    assert Participant.query.count() == 0
