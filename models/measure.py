from extensions import db
from models.base import SoftDeleteMixin, TimestampMixin, iso

MEASURE_STATUSES = ("geplant", "aktiv", "beendet")


class Measure(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "measures"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    number = db.Column(db.String(80), nullable=True)  # z.B. Maßnahmenummer der Agentur/Jobcenter
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="geplant", index=True)
    capacity = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text, nullable=True)

    location = db.relationship("Location")
    enrollments = db.relationship("Enrollment", back_populates="measure", lazy="dynamic")

    def active_enrollment_count(self) -> int:
        from models.enrollment import Enrollment

        return self.enrollments.filter(
            Enrollment.is_deleted.is_(False), Enrollment.status == "aktiv"
        ).count()

    def to_dict(self, with_counts=False):
        data = {
            "id": self.id,
            "name": self.name,
            "number": self.number,
            "location_id": self.location_id,
            "location_name": self.location.name if self.location else None,
            "start_date": iso(self.start_date),
            "end_date": iso(self.end_date),
            "status": self.status,
            "capacity": self.capacity,
            "description": self.description,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
        if with_counts:
            data["active_enrollments"] = self.active_enrollment_count()
        return data
