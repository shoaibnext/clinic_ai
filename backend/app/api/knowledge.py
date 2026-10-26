import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_clinic
from app.ai.rag import ingest_document_chunks
from app.database.database import get_db
from app.database.models import Clinic
from app.schemas.knowledge import (
    DocumentCreate,
    DocumentRead,
    KnowledgeBaseCreate,
    KnowledgeBaseRead,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
)
from app.services import knowledge_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/bases", response_model=KnowledgeBaseRead, status_code=status.HTTP_201_CREATED)
async def post_knowledge_base(
    payload: KnowledgeBaseCreate,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    return knowledge_service.create_knowledge_base(
        db, clinic, name=payload.name, description=payload.description
    )


@router.get("/bases", response_model=list[KnowledgeBaseRead])
async def get_knowledge_bases(
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    return knowledge_service.list_knowledge_bases(db, clinic)


@router.post("/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def post_document(
    payload: DocumentCreate,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    """Add a document (paste text). The chunker runs synchronously; embeddings are
    created at ingest time so retrieval stays fast."""
    try:
        document = knowledge_service.add_document(
            db,
            clinic,
            knowledge_base_id=payload.knowledge_base_id,
            filename=payload.filename,
            content=payload.content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    from app.database.models import DocumentChunk

    chunks = [
        chunk.content
        for chunk in db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    ]
    try:
        await ingest_document_chunks(
            db, clinic_id=clinic.id, document=document, chunks=chunks
        )
        document.status = "processed"
        db.add(document)
        db.commit()
        db.refresh(document)
    except Exception as exc:
        document.status = "failed"
        db.add(document)
        db.commit()
        logger.warning("Document ingest failed: %s", exc)
    return document


@router.get("/documents", response_model=list[DocumentRead])
async def get_documents(
    knowledge_base_id: int | None = None,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    return knowledge_service.list_documents(db, clinic, knowledge_base_id=knowledge_base_id)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    deleted = knowledge_service.delete_document(db, clinic, document_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    payload: KnowledgeSearchRequest,
    clinic: Clinic = Depends(get_current_clinic),
    db: Session = Depends(get_db),
):
    from app.ai.rag import retrieve

    try:
        results = await retrieve(db, clinic.id, payload.query, k=payload.k)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Retrieval unavailable: {exc}",
        ) from exc
    return KnowledgeSearchResponse(
        query=payload.query,
        results=[KnowledgeSearchResult(**r) for r in results],
    )