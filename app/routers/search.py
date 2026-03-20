from fastapi import APIRouter, HTTPException
from app.db import get_collection
from app.schemas import SearchRequest, SearchResponse, DocumentResult

router = APIRouter()


@router.post("", response_model=SearchResponse)
def semantic_search(req: SearchRequest):
    """
    Search for semantically similar documents using natural language query.
    Optionally filter by metadata using the `where` field.
    """
    try:
        collection = get_collection(req.collection)

        if collection.count() == 0:
            return SearchResponse(query=req.query, results=[], total=0)

        results = collection.query(
            query_texts=[req.query],
            n_results=min(req.top_k, collection.count()),
            where=req.where,
            include=["documents", "metadatas", "distances"],
        )

        documents = [
            DocumentResult(
                id=results["ids"][0][i],
                document=results["documents"][0][i],
                metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                distance=results["distances"][0][i],
            )
            for i in range(len(results["ids"][0]))
        ]

        return SearchResponse(
            query=req.query,
            results=documents,
            total=len(documents),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
