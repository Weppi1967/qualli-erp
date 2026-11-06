"""Beispieldaten für Entwicklung und Test.

    python seed.py            -> legt Beispieldaten an (nur wenn noch keine vorhanden)
    python seed.py --remove   -> entfernt alle Beispieldaten wieder (hart, nur Beispieldaten)

Alle Beispiel-Teilnehmer tragen custom_fields.sample = true und sind frei erfunden.
"""
import random
import sys
from datetime import date, timedelta

from extensions import db
from models import Employee, Enrollment, Location, Measure, Participant, ParticipantChange, User
from utils.participant_service import create_participant

FIRST_NAMES_W = ["Anna", "Lena", "Sarah", "Julia", "Laura", "Marie", "Sophie", "Lea", "Hannah", "Emma", "Mia", "Elif", "Fatma", "Olga", "Natalia", "Sandra", "Petra", "Nicole", "Sabine", "Katharina", "Ayse", "Irina", "Melanie", "Jasmin"]
FIRST_NAMES_M = ["Lukas", "Jonas", "Leon", "Finn", "Paul", "Tim", "Jan", "Max", "Mehmet", "Ahmed", "Ali", "Sergej", "Andreas", "Thomas", "Michael", "Stefan", "Markus", "Daniel", "Kevin", "Dennis", "Yusuf", "Pawel", "Oleksandr", "Mustafa"]
LAST_NAMES = ["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker", "Schulz", "Hoffmann", "Koch", "Richter", "Klein", "Wolf", "Schröder", "Neumann", "Schwarz", "Braun", "Zimmermann", "Krüger", "Hartmann", "Lange", "Werner", "Krause", "Meier", "Lehmann", "Yilmaz", "Kaya", "Demir", "Nowak", "Kowalski", "Popov", "Ivanova", "Lindemann", "Brinkmann", "Kampmann", "Niemeyer", "Rohlfing", "Tiemann", "Wehking"]
STREETS = ["Hauptstraße", "Bahnhofstraße", "Kirchweg", "Lindenallee", "Mindener Straße", "Am Markt", "Gartenstraße", "Schulstraße", "Bergstraße", "Mühlenweg"]
CITY_ZIP = {"Minden": "32423", "Lübbecke": "32312", "Espelkamp": "32339", "Bad Oeynhausen": "32545", "Porta Westfalica": "32457", "Petershagen": "32469"}
MEASURE_TYPES = ["Aktivcenter", "Profiling & Bewerbungscoaching", "Perspektive Arbeit", "Job-Speed-Dating", "AVGS Einzelcoaching", "Berufliche Orientierung U25", "Sprachförderung Beruf", "Integrationscoaching"]


def _sample_participant(rng: random.Random, location: Location):
    female = rng.random() < 0.5
    first = rng.choice(FIRST_NAMES_W if female else FIRST_NAMES_M)
    last = rng.choice(LAST_NAMES)
    birth = date(1965, 1, 1) + timedelta(days=rng.randint(0, 365 * 40))
    city = location.city or "Minden"
    return {
        "basic_info": {
            "salutation": "frau" if female else "herr",
            "first_name": first,
            "last_name": last,
            "birth_date": birth.isoformat(),
            "gender": "w" if female else "m",
            "phone": f"0571 {rng.randint(100000, 999999)}",
            "email": f"{first.lower()}.{last.lower()}@beispiel.invalid".replace("ü", "ue").replace("ö", "oe").replace("ä", "ae"),
            "cost_unit": rng.choice(["jobcenter", "jobcenter", "agentur", "drv"]),
        },
        "address_info": {
            "street": f"{rng.choice(STREETS)} {rng.randint(1, 120)}",
            "zip": CITY_ZIP.get(city, "32423"),
            "city": city,
        },
        "characteristics": {
            "school_degree": rng.choice(["ohne", "hauptschule", "hauptschule", "realschule", "fachabitur", "abitur", "ausland"]),
            "driving_license": rng.choice([[], ["B"], ["B"], ["B", "BE"], ["AM"], ["B", "C", "CE"]]),
            "marital_status": rng.choice(["ledig", "verheiratet", "geschieden"]),
            "children": rng.choice([0, 0, 1, 2, 3]),
            "german_level": rng.choice(["muttersprache", "muttersprache", "B2", "B1", "A2"]),
        },
        "custom_fields": {"sample": True},
    }


def seed_sample_data(n_participants=210, n_measures=18, seed=42):
    if any((p.custom_fields or {}).get("sample") for p in Participant.query.all()):
        return "Beispieldaten sind bereits vorhanden – nichts zu tun."

    rng = random.Random(seed)
    admin = User.query.filter_by(role="admin").first()
    locations = Location.query.order_by(Location.id).all()
    if not locations:
        raise RuntimeError("Keine Standorte vorhanden – bitte zuerst die App einmal starten.")

    today = date.today()
    measures = []
    for i in range(n_measures):
        loc = locations[i % len(locations)]
        start = today - timedelta(days=rng.randint(-60, 400))
        end = start + timedelta(days=rng.choice([90, 180, 270, 365]))
        status = "geplant" if start > today else ("beendet" if end < today else "aktiv")
        m = Measure(
            name=f"{MEASURE_TYPES[i % len(MEASURE_TYPES)]} {loc.name}",
            number=f"MN-{today.year}-{i + 1:03d}",
            location_id=loc.id,
            start_date=start,
            end_date=end,
            status=status,
            capacity=rng.choice([12, 15, 20, 25]),
            description="Beispielmaßnahme",
        )
        db.session.add(m)
        measures.append(m)
    db.session.flush()

    participants = []
    for i in range(n_participants):
        loc = locations[i % len(locations)]
        participants.append(create_participant(admin, loc.id, _sample_participant(rng, loc), action="import"))
    db.session.flush()

    enrollments = 0
    for p in participants:
        if rng.random() > 0.62:
            continue
        options = [m for m in measures if m.location_id == p.location_id] or measures
        m = rng.choice(options)
        if m.status == "geplant":
            status, entry, exit_ = "aktiv", m.start_date, None
        elif m.status == "beendet":
            status = rng.choice(["beendet", "beendet", "abgebrochen"])
            entry, exit_ = m.start_date, m.end_date
        else:
            status = rng.choice(["aktiv", "aktiv", "aktiv", "abgebrochen"])
            entry = m.start_date + timedelta(days=rng.randint(0, 30))
            exit_ = None if status == "aktiv" else min(today, entry + timedelta(days=rng.randint(5, 60)))
        db.session.add(Enrollment(participant_id=p.id, measure_id=m.id, status=status, enrollment_date=entry, exit_date=exit_))
        enrollments += 1

    for loc in locations[:3]:
        db.session.add(Employee(location_id=loc.id, name=f"Coach {loc.name}", role="Jobcoach", start_date=today - timedelta(days=500)))

    db.session.commit()
    return f"Angelegt: {n_participants} Teilnehmer, {n_measures} Maßnahmen, {enrollments} Zuordnungen."


def remove_sample_data():
    sample_ids = [p.id for p in Participant.query.all() if (p.custom_fields or {}).get("sample")]
    if not sample_ids:
        return "Keine Beispieldaten gefunden."
    Enrollment.query.filter(Enrollment.participant_id.in_(sample_ids)).delete(synchronize_session=False)
    ParticipantChange.query.filter(ParticipantChange.participant_id.in_(sample_ids)).delete(synchronize_session=False)
    Participant.query.filter(Participant.id.in_(sample_ids)).delete(synchronize_session=False)
    sample_measures = Measure.query.filter(Measure.description == "Beispielmaßnahme").all()
    for m in sample_measures:
        if m.enrollments.count() == 0:
            db.session.delete(m)
    Employee.query.filter(Employee.name.like("Coach %")).delete(synchronize_session=False)
    db.session.commit()
    return f"Entfernt: {len(sample_ids)} Beispiel-Teilnehmer und zugehörige Beispieldaten."


if __name__ == "__main__":
    from app import create_app

    app = create_app()
    with app.app_context():
        print(remove_sample_data() if "--remove" in sys.argv else seed_sample_data())
