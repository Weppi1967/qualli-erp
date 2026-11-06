from extensions import db
from models.base import TimestampMixin, iso


class Location(TimestampMixin, db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    address = db.Column(db.String(200), nullable=True)
    zip = db.Column(db.String(10), nullable=True)
    city = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "zip": self.zip,
            "city": self.city,
            "phone": self.phone,
            "is_active": self.is_active,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
