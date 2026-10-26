from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base

if TYPE_CHECKING:
    from app.database.models.appointment import Appointment
    from app.database.models.conversation import Conversation


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("clinic_id", "phone_number", name="uq_patient_clinic_phone"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(150), default="")
    phone_number: Mapped[str] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(10), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="patient")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="patient")
