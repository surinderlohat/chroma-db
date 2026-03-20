from fastapi import APIRouter, HTTPException
from app.db import get_client, list_collections

router = APIRouter()


@router.get("/health")
def health_check():
    """Check if the embedded ChromaDB is operational."""
    try:
        collections = list_collections()
        return {
            "status": "ok",
            "chromadb": "embedded",
            "collections": len(collections),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"ChromaDB error: {e}")
