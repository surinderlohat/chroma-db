from fastapi import APIRouter, HTTPException
from app.db import get_collection, safe_upsert, safe_delete
from app.schemas import UpsertRequest, DeleteRequest, StatusResponse

router = APIRouter()

BATCH_SIZE = 256


@router.post("/upsert", response_model=StatusResponse)
async def upsert_documents(req: UpsertRequest):
    """
    Add or update documents in a collection.
    - If an ID already exists, it gets updated.
    - If it doesn't exist, it gets added.
    - Embeddings are generated automatically.
    - Writes are serialized via asyncio lock — safe for concurrent requests.
    """
    if len(req.ids) != len(req.documents):
        raise HTTPException(
            status_code=422,
            detail=f"ids and documents length mismatch: {len(req.ids)} vs {len(req.documents)}",
        )
    if req.metadatas and len(req.metadatas) != len(req.ids):
        raise HTTPException(
            status_code=422,
            detail=f"metadatas length must match ids: {len(req.metadatas)} vs {len(req.ids)}",
        )

    try:
        collection = get_collection(req.collection)
        total = len(req.ids)

        for i in range(0, total, BATCH_SIZE):
            await safe_upsert(
                collection,
                ids=req.ids[i : i + BATCH_SIZE],
                documents=req.documents[i : i + BATCH_SIZE],
                metadatas=req.metadatas[i : i + BATCH_SIZE] if req.metadatas else None,
            )

        return StatusResponse(
            status="ok",
            message=f"Upserted {total} documents into '{req.collection}'. Total: {collection.count()}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete", response_model=StatusResponse)
async def delete_documents(req: DeleteRequest):
    """
    Delete documents by their IDs.
    Writes are serialized via asyncio lock — safe for concurrent requests.
    """
    try:
        collection = get_collection(req.collection)
        await safe_delete(collection, ids=req.ids)
        return StatusResponse(
            status="ok",
            message=f"Deleted {len(req.ids)} documents from '{req.collection}'. Remaining: {collection.count()}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
