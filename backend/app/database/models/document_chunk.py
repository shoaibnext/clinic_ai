from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    # Embedding is stored as JSON so retrieval works on SQLite and PostgreSQL.
    # For scale, production can switch to pgvector: use
    #   from pgvector.sqlalchemy import Vector
    #   embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    # and replace the Python cosine similarity with `embedding <=> :query_embedding`.
    id: Mapped[int] = mapped_column(primary_key=True)
    clinic_id: Mapped[int] = mapped_column(ForeignKey("clinics.id"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())