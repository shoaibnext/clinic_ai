from sqlalchemy.orm import Session

from app.database.models import Clinic, Document, DocumentChunk, KnowledgeBase


def _split_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Very small chunker: split on blank lines, then merge up to chunk_size chars."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        if len(buffer) + len(paragraph) + 2 <= chunk_size:
            buffer = f"{buffer}\n\n{paragraph}" if buffer else paragraph
            continue
        if buffer:
            chunks.append(buffer)
        if len(paragraph) > chunk_size:
            words = paragraph.split()
            current = ""
            for word in words:
                if len(current) + len(word) + 1 > chunk_size and current:
                    chunks.append(current)
                    current = current[-overlap:] + " "
                current = f"{current} {word}".strip()
            if current:
                buffer = current
        else:
            buffer = paragraph
    if buffer:
        chunks.append(buffer)
    return [c for c in chunks if c.strip()]


def create_knowledge_base(
    db: Session, clinic: Clinic, *, name: str, description: str | None = None
) -> KnowledgeBase:
    kb = KnowledgeBase(clinic_id=clinic.id, name=name, description=description)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def list_knowledge_bases(db: Session, clinic: Clinic) -> list[KnowledgeBase]:
    return db.query(KnowledgeBase).filter(KnowledgeBase.clinic_id == clinic.id).all()


def get_knowledge_base(db: Session, clinic: Clinic, kb_id: int) -> KnowledgeBase | None:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None or kb.clinic_id != clinic.id:
        return None
    return kb


def add_document(
    db: Session,
    clinic: Clinic,
    *,
    knowledge_base_id: int,
    filename: str,
    content: str,
    content_type: str | None = None,
) -> Document:
    kb = get_knowledge_base(db, clinic, knowledge_base_id)
    if kb is None:
        raise ValueError("Knowledge base not found")
    document = Document(
        clinic_id=clinic.id,
        knowledge_base_id=kb.id,
        filename=filename,
        content_type=content_type,
        status="pending",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Store the raw text on the first chunk row so ingestion has the content.
    # (A filesystem/object store would be used in production.)
    chunks = _split_text(content)
    for index, chunk in enumerate(chunks):
        db.add(
            DocumentChunk(
                clinic_id=clinic.id,
                document_id=document.id,
                content=chunk,
                chunk_index=index,
            )
        )
    db.commit()
    return document


def list_documents(db: Session, clinic: Clinic, knowledge_base_id: int | None = None) -> list[Document]:
    query = db.query(Document).filter(Document.clinic_id == clinic.id)
    if knowledge_base_id is not None:
        query = query.filter(Document.knowledge_base_id == knowledge_base_id)
    return query.order_by(Document.created_at.desc()).all()


def get_document(db: Session, clinic: Clinic, document_id: int) -> Document | None:
    document = db.get(Document, document_id)
    if document is None or document.clinic_id != clinic.id:
        return None
    return document


def delete_document(db: Session, clinic: Clinic, document_id: int) -> bool:
    document = get_document(db, clinic, document_id)
    if document is None:
        return False
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
    db.delete(document)
    db.commit()
    return True