# Copyright (c) 2025 Surinder Singh (https://github.com/surinderlohat)
# Licensed under the MIT License. See LICENSE file in the project root.
from fastapi import APIRouter, HTTPException
from app.db import get_collection, safe_upsert, safe_delete
from app.logger import get_logger
from app.memory import check_memory_limit
from app.schemas import UpsertRequest, SingleUpsertRequest, DeleteRequest, StatusResponse

logger = get_logger(__name__)
router = APIRouter()
BATCH_SIZE = 256


@router.post("/upsert", response_model=StatusResponse)
async def upsert_single(req: SingleUpsertRequest):
    """Insert or update a single document."""
    try:
        check_memory_limit()  # reject if memory too high
        logger.info(f"Upserting document '{req.id}' into collection '{req.collection}'")
        collection = get_collection(req.collection)
        await safe_upsert(
            collection,
            ids=[req.id],
            documents=[req.text],
            metadatas=[req.metadata] if req.metadata else None,
        )
        total = collection.count()
        logger.info(f"Upserted '{req.id}' successfully. Collection total: {total}")
        return StatusResponse(
            status="ok",
            message=f"Upserted document '{req.id}' into '{req.collection}'. Total: {total}",
        )
    except MemoryError as e:
        raise HTTPException(status_code=507, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to upsert document '{req.id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upsert/bulk", response_model=StatusResponse)
async def upsert_bulk(req: UpsertRequest):
    """Insert or update multiple documents in one call."""
    total = len(req.documents)
    logger.info(f"Bulk upsert of {total} documents into collection '{req.collection}'")
    try:
        check_memory_limit()  # reject if memory too high
        collection = get_collection(req.collection)
        for i in range(0, total, BATCH_SIZE):
            batch = req.documents[i : i + BATCH_SIZE]
            logger.debug(f"Upserting batch {i // BATCH_SIZE + 1} ({len(batch)} docs)")
            await safe_upsert(
                collection,
                ids=[doc.id for doc in batch],
                documents=[doc.text for doc in batch],
                metadatas=[doc.metadata for doc in batch],
            )
        count = collection.count()
        logger.info(f"Bulk upsert complete. {total} docs processed. Collection total: {count}")
        return StatusResponse(
            status="ok",
            message=f"Upserted {total} documents into '{req.collection}'. Total: {count}",
        )
    except MemoryError as e:
        raise HTTPException(status_code=507, detail=str(e))
    except Exception as e:
        logger.error(f"Bulk upsert failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete", response_model=StatusResponse)
async def delete_documents(req: DeleteRequest):
    """Delete documents by their IDs."""
    logger.info(f"Deleting {len(req.ids)} documents from collection '{req.collection}'")
    try:
        collection = get_collection(req.collection)
        await safe_delete(collection, ids=req.ids)
        remaining = collection.count()
        logger.info(f"Deleted {len(req.ids)} docs. Remaining: {remaining}")
        return StatusResponse(
            status="ok",
            message=f"Deleted {len(req.ids)} documents from '{req.collection}'. Remaining: {remaining}",
        )
    except Exception as e:
        logger.error(f"Delete failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
