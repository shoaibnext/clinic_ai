from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class DoctorService(Base):
    __tablename__ = "doctor_services"
    __table_args__ = (
        UniqueConstraint("clinic_id", "doctor_id", "service_id", name="uq_doctor_service"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), index=True)

    service: Mapped["Service"] = relationship(back_populates="doctor_links")  # noqa: F821