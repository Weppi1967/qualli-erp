"""Gemeinsame Logik für Anlage/Änderung von Teilnehmern inkl. Audit-Trail."""
from extensions import db
from models import JSON_SECTIONS, Participant, ParticipantChange
from utils.validators import normalize_key


def diff_sections(old: dict, new: dict) -> dict:
    changes = {}
    for section in JSON_SECTIONS:
        before = old.get(section) or {}
        after = new.get(section) or {}
        for key in sorted(set(before) | set(after)):
            if before.get(key) != after.get(key):
                changes.setdefault(section, {})[key] = {"old": before.get(key), "new": after.get(key)}
    return changes


def snapshot(participant: Participant) -> dict:
    return {s: dict(getattr(participant, s) or {}) for s in JSON_SECTIONS}


def log_change(participant, user, action, changes):
    db.session.add(
        ParticipantChange(
            participant_id=participant.id,
            changed_by=user.id if user else None,
            action=action,
            changes_json=changes,
        )
    )


def create_participant(user, location_id, sections, action="create") -> Participant:
    participant = Participant(location_id=location_id, created_by=user.id if user else None)
    for section in JSON_SECTIONS:
        setattr(participant, section, sections.get(section) or {})
    participant.refresh_derived()
    db.session.add(participant)
    db.session.flush()
    changes = diff_sections({}, snapshot(participant))
    changes["location_id"] = {"old": None, "new": location_id}
    log_change(participant, user, action, changes)
    return participant


def name_key(first, last):
    return (normalize_key(first), normalize_key(last))


def find_duplicates(first, last, birth_date=None, exclude_id=None):
    """Dublettenprüfung über Vor- und Nachname (Geburtsdatum als Unterscheidung,
    falls bei beiden Datensätzen vorhanden)."""
    if not first or not last:
        return []
    query = Participant.query.filter(
        Participant.is_deleted.is_(False),
        db.func.lower(Participant.first_name) == first.strip().lower(),
        db.func.lower(Participant.last_name) == last.strip().lower(),
    )
    if exclude_id:
        query = query.filter(Participant.id != exclude_id)
    result = []
    for p in query.all():
        other_birth = (p.basic_info or {}).get("birth_date")
        if birth_date and other_birth and other_birth != birth_date:
            continue
        result.append(p)
    return result
