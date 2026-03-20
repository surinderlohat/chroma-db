# Copyright (c) 2025 Surinder Singh (https://github.com/surinderlohat)
# Licensed under the MIT License. See LICENSE file in the project root.
from fastapi import APIRouter, HTTPException
from app.db import list_collections
from app.logger import get_logger
from app.memory import get_memory_mb, MEMORY_WARN_MB, MEMORY_LIMIT_MB

logger = get_logger(__name__)
router = APIRouter()


@router.get("/health")
def health_check():
    """Check if the embedded ChromaDB is operational."""
    logger.debug("Health check requested")
    try:
        collections = list_collections()
        usage_mb = get_memory_mb()
        status = "ok"

        if usage_mb >= MEMORY_LIMIT_MB:
            status = "critical"
        elif usage_mb >= MEMORY_WARN_MB:
            status = "warning"

        logger.debug(
            f"Health check passed. Collections: {len(collections)}, RAM: {usage_mb:.1f} MB"
        )
        return {
            "status": status,
            "chromadb": "embedded",
            "collections": len(collections),
            "memory_mb": round(usage_mb, 1),
            "memory_warn_mb": MEMORY_WARN_MB,
            "memory_limit_mb": MEMORY_LIMIT_MB,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"ChromaDB error: {e}")
