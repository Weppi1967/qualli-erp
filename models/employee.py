from extensions import db
from models.base import SoftDeleteMixin, TimestampMixin, iso


class Employee(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(120), nullable=True)  # z.B. Coach, Jobcoach, Verwaltung
    email = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    location = db.relationship("Location")

    def to_dict(self):
        return {
            "id": self.id,
            "location_id": self.location_id,
            "location_name": self.location.name if self.location else None,
            "name": self.name,
            "role": self.role,
            "email": self.email,
            "phone": self.phone,
            "start_date": iso(self.start_date),
            "user_id": self.user_id,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
