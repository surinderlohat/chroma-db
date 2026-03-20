# Copyright (c) 2025 Surinder Singh (https://github.com/surinderlohat)
# Licensed under the MIT License. See LICENSE file in the project root.
from fastapi import APIRouter, HTTPException
from app.db import get_collection
from app.logger import get_logger
from app.schemas import SearchRequest, SearchResponse, DocumentResult

logger = get_logger(__name__)
router = APIRouter()


@router.post("", response_model=SearchResponse)
def semantic_search(req: SearchRequest):
    """Search for semantically similar documents using natural language query."""
    logger.info(f"Search query='{req.query}' top_k={req.top_k} collection='{req.collection}'")
    try:
        collection = get_collection(req.collection)

        if collection.count() == 0:
            logger.warning(f"Search on empty collection '{req.collection}'")
            return SearchResponse(query=req.query, results=[], total=0)

        results = collection.query(
            query_texts=[req.query],
            n_results=min(req.top_k, collection.count()),
            where=req.where,
            include=["documents", "metadatas", "distances"],
        )

        # Use from_chroma() factory — maps ChromaDB's 'document' key to our 'text' field
        documents = [
            DocumentResult.from_chroma(
                id=results["ids"][0][i],
                document=results["documents"][0][i],  # ChromaDB always returns 'document'
                metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                distance=results["distances"][0][i],
            )
            for i in range(len(results["ids"][0]))
        ]

        logger.info(f"Search returned {len(documents)} results for query='{req.query}'")
        logger.debug(f"Result IDs: {[d.id for d in documents]}")

        return SearchResponse(query=req.query, results=documents, total=len(documents))
    except Exception as e:
        logger.error(f"Search failed for query='{req.query}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
