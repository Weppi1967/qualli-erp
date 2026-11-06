from extensions import db
from models.base import SoftDeleteMixin, TimestampMixin, iso

JSON_SECTIONS = ("basic_info", "address_info", "characteristics", "custom_fields")


class Participant(TimestampMixin, SoftDeleteMixin, db.Model):
    """Teilnehmer:in. Fachliche Felder liegen flexibel in JSON-Spalten,
    damit neue Felder ohne Datenbank-Migration ergänzt werden können
    (Feldkonfiguration: config/participant_fields.json)."""

    __tablename__ = "participants"

    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False, index=True)
    basic_info = db.Column(db.JSON, nullable=False, default=dict)
    address_info = db.Column(db.JSON, nullable=False, default=dict)
    characteristics = db.Column(db.JSON, nullable=False, default=dict)
    custom_fields = db.Column(db.JSON, nullable=False, default=dict)

    # Denormalisierte Spalten für schnelle Suche/Sortierung und Dublettenprüfung.
    first_name = db.Column(db.String(120), nullable=True, index=True)
    last_name = db.Column(db.String(120), nullable=True, index=True)
    search_text = db.Column(db.Text, nullable=False, default="")

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    location = db.relationship("Location")
    enrollments = db.relationship("Enrollment", back_populates="participant", lazy="dynamic")

    def refresh_derived(self):
        basic = self.basic_info or {}
        address = self.address_info or {}
        self.first_name = (basic.get("first_name") or "").strip() or None
        self.last_name = (basic.get("last_name") or "").strip() or None
        parts = [
            basic.get("first_name"),
            basic.get("last_name"),
            basic.get("birth_date"),
            basic.get("email"),
            basic.get("phone"),
            basic.get("customer_number"),
            address.get("city"),
            address.get("zip"),
            address.get("street"),
        ]
        self.search_text = " ".join(str(p) for p in parts if p).lower()

    @property
    def display_name(self) -> str:
        return ", ".join(p for p in (self.last_name, self.first_name) if p) or f"#{self.id}"

    def to_dict(self, include_location=True):
        data = {
            "id": self.id,
            "location_id": self.location_id,
            "display_name": self.display_name,
            "basic_info": self.basic_info or {},
            "address_info": self.address_info or {},
            "characteristics": self.characteristics or {},
            "custom_fields": self.custom_fields or {},
            "is_deleted": self.is_deleted,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
        if include_location:
            data["location_name"] = self.location.name if self.location else None
        return data
