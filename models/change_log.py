from extensions import db
from models.base import iso, utcnow


class ParticipantChange(db.Model):
    """Audit-Trail: jede Anlage/Änderung/Löschung eines Teilnehmers."""

    __tablename__ = "participant_changes"

    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey("participants.id"), nullable=False, index=True)
    changed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(20), nullable=False)  # create | update | delete | import
    changes_json = db.Column(db.JSON, nullable=False, default=dict)
    timestamp = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "participant_id": self.participant_id,
            "changed_by": self.changed_by,
            "changed_by_name": self.user.username if self.user else None,
            "action": self.action,
            "changes": self.changes_json,
            "timestamp": iso(self.timestamp),
        }


class TokenBlocklist(db.Model):
    """Abgemeldete (widerrufene) JWTs."""

    __tablename__ = "token_blocklist"

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(64), nullable=False, unique=True, index=True)
    token_type = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
