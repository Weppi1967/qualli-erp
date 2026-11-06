from extensions import db
from models.base import SoftDeleteMixin, TimestampMixin, iso

ENROLLMENT_STATUSES = ("aktiv", "beendet", "abgebrochen")


class Enrollment(TimestampMixin, SoftDeleteMixin, db.Model):
    """Zuordnung Teilnehmer:in ↔ Maßnahme."""

    __tablename__ = "enrollments"

    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey("participants.id"), nullable=False, index=True)
    measure_id = db.Column(db.Integer, db.ForeignKey("measures.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="aktiv", index=True)
    enrollment_date = db.Column(db.Date, nullable=False)
    exit_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    participant = db.relationship("Participant", back_populates="enrollments")
    measure = db.relationship("Measure", back_populates="enrollments")

    def to_dict(self):
        return {
            "id": self.id,
            "participant_id": self.participant_id,
            "participant_name": self.participant.display_name if self.participant else None,
            "measure_id": self.measure_id,
            "measure_name": self.measure.name if self.measure else None,
            "measure_status": self.measure.status if self.measure else None,
            "location_id": self.measure.location_id if self.measure else None,
            "location_name": self.measure.location.name if self.measure and self.measure.location else None,
            "status": self.status,
            "enrollment_date": iso(self.enrollment_date),
            "exit_date": iso(self.exit_date),
            "notes": self.notes,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
