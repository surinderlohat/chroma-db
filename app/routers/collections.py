from fastapi import APIRouter, HTTPException
from app.db import get_collection, list_collections, delete_collection
from app.schemas import CollectionListResponse, CollectionInfo, StatusResponse

router = APIRouter()


@router.get("", response_model=CollectionListResponse)
def get_all_collections():
    """List all collections with their document counts."""
    names = list_collections()
    collections = []
    for name in names:
        col = get_collection(name)
        collections.append(CollectionInfo(name=name, count=col.count()))
    return CollectionListResponse(collections=collections, total=len(collections))


@router.get("/{name}", response_model=CollectionInfo)
def get_single_collection(name: str):
    """Get info about a specific collection."""
    try:
        col = get_collection(name)
        return CollectionInfo(name=name, count=col.count())
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Collection '{name}' not found: {e}")


@router.delete("/{name}", response_model=StatusResponse)
def drop_collection(name: str):
    """Delete an entire collection and all its documents."""
    try:
        delete_collection(name)
        return StatusResponse(status="ok", message=f"Collection '{name}' deleted.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
