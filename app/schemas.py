from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


# ── Documents ──────────────────────────────────────────────

class UpsertRequest(BaseModel):
    ids: list[str]
    documents: list[str]
    metadatas: list[dict[str, Any]] | None = None
    collection: str = "default"

    model_config = {
        "json_schema_extra": {
            "example": {
                "ids": ["doc_1", "doc_2"],
                "documents": ["Hello world", "FastAPI is great"],
                "metadatas": [{"source": "wiki"}, {"source": "blog"}],
                "collection": "default",
            }
        }
    }


class DeleteRequest(BaseModel):
    ids: list[str]
    collection: str = "default"


class DocumentResult(BaseModel):
    id: str
    document: str
    metadata: dict[str, Any]
    distance: float


# ── Search ─────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=10, ge=1, le=100)
    collection: str = "default"
    where: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata filter e.g. {\"source\": \"wiki\"}"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "What is machine learning?",
                "top_k": 5,
                "collection": "default",
                "where": {"source": "wiki"},
            }
        }
    }


class SearchResponse(BaseModel):
    query: str
    results: list[DocumentResult]
    total: int


# ── Collections ────────────────────────────────────────────

class CollectionInfo(BaseModel):
    name: str
    count: int


class CollectionListResponse(BaseModel):
    collections: list[CollectionInfo]
    total: int


# ── Generic ────────────────────────────────────────────────

class StatusResponse(BaseModel):
    status: str
    message: str
