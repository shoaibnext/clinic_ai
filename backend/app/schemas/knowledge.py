from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class KnowledgeBaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clinic_id: int
    name: str
    description: str | None
    created_at: datetime


class DocumentCreate(BaseModel):
    knowledge_base_id: int = Field(gt=0)
    filename: str = Field(min_length=1)
    content: str = Field(min_length=1)


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    clinic_id: int
    knowledge_base_id: int
    filename: str
    content_type: str | None
    status: str
    created_at: datetime


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchResult(BaseModel):
    document_id: int
    chunk_index: int
    content: str
    score: float


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: list[KnowledgeSearchResult]