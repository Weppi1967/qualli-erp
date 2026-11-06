from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models.base import TimestampMixin, iso

ROLES = ("admin", "location_manager", "employee")

# Zusätzliche Standorte für Standortleitungen (Multi-Standort-Zugriff).
user_locations = db.Table(
    "user_locations",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    db.Column("location_id", db.Integer, db.ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True),
)


class User(TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="employee")
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=True)
    email = db.Column(db.String(200), nullable=True)
    full_name = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime, nullable=True)

    location = db.relationship("Location", foreign_keys=[location_id])
    extra_locations = db.relationship("Location", secondary=user_locations, lazy="selectin")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def assigned_location_ids(self) -> set[int]:
        ids = {loc.id for loc in self.extra_locations}
        if self.location_id:
            ids.add(self.location_id)
        return ids

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "location_id": self.location_id,
            "location_ids": sorted(self.assigned_location_ids()),
            "email": self.email,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "last_login_at": iso(self.last_login_at),
            "created_at": iso(self.created_at),
        }
