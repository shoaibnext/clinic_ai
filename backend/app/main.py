from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    ai,
    appointments,
    auth,
    availability,
    clinics,
    conversations,
    doctors,
    health,
    knowledge,
    leads,
    patients,
    services,
    whatsapp,
)
from app.core.config import settings
from app.core.logging import setup_logging
from app.database import models  # noqa: F401  (register models)
from app.database.database import Base, engine

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(clinics.router)
app.include_router(doctors.router)
app.include_router(services.router)
app.include_router(patients.router)
app.include_router(appointments.router)
app.include_router(leads.router)
app.include_router(conversations.router)
app.include_router(availability.router)
app.include_router(knowledge.router)
app.include_router(whatsapp.router)
app.include_router(ai.router)


@app.get("/")
async def root():
    return {
        "message": "Clinic AI Receptionist API",
        "version": "1.0.0",
        "service": "AI WhatsApp receptionist for clinics (multi-tenant)",
    }