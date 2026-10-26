import os

# Force SQLite for the test process before the app engine is constructed.
os.environ["DATABASE_URL"] = "sqlite:///./clinicai_test.db"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import models  # noqa: F401  (register all models)
from app.database.database import Base, get_db
from app.services import clinic_service, doctor_service, service_service, availability_service


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def clinic(db_session):
    from app.services.clinic_service import create_clinic

    return create_clinic(
        db_session,
        name="ABC Dental Clinic",
        slug="abc-dental",
        phone="+15550100000",
        address="123 Wellness Avenue",
        admin_email="admin@abc.test",
        admin_password="Secret123!",
        whatsapp_phone_number_id="123456789",
        emergency_instructions="In an emergency call 112 immediately.",
    )


@pytest.fixture()
def other_clinic(db_session):
    from app.services.clinic_service import create_clinic

    return create_clinic(
        db_session,
        name="Sunrise Clinic",
        slug="sunrise",
        admin_email="admin@sunrise.test",
        admin_password="Secret456!",
        whatsapp_phone_number_id="987654321",
    )


@pytest.fixture()
def patient(db_session, clinic):
    from app.services import patient_service

    return patient_service.create_patient(
        db_session, clinic, full_name="Ali Raza", phone_number="+15550101111", language="en"
    )


@pytest.fixture()
def clinic_headers(clinic):
    return {"X-API-Key": clinic.api_key}


@pytest.fixture()
def other_clinic_headers(other_clinic):
    return {"X-API-Key": other_clinic.api_key}


@pytest.fixture()
def service(db_session, clinic):
    return service_service.create_service(
        db_session, clinic, name="Dental Cleaning", duration_minutes=30, price="1500"
    )


@pytest.fixture()
def doctor(db_session, clinic, service):
    return doctor_service.create_doctor(
        db_session,
        clinic,
        name="Dr. Khan",
        title="Dentist",
        specialty="Dentistry",
        service_ids=[service.id],
    )


@pytest.fixture()
def availability(db_session, clinic, doctor, service):
    """Monday-Friday 09:00-17:00 recurring window."""
    return availability_service.create_availability(
        db_session,
        clinic,
        doctor_id=doctor.id,
        service_id=service.id,
        weekday=0,
        start_time=__import__("datetime").time(9, 0),
        end_time=__import__("datetime").time(17, 0),
        is_recurring=True,
    )