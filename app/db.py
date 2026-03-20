from __future__ import annotations

import asyncio
import os
from pathlib import Path

import chromadb
from chromadb import Collection
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

MODEL_NAME         = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "/app/chromadb")
DEFAULT_COLLECTION = os.getenv("DEFAULT_COLLECTION", "default")

_CLIENT:       chromadb.PersistentClient | None = None
_EMBEDDING_FN: SentenceTransformerEmbeddingFunction | None = None

# Single async lock — serializes all write operations (upsert / delete)
# asyncio.Lock is the right fit here because FastAPI runs in a single async process.
# No need for filelock (multi-process) or threading.Lock (blocks event loop).
_WRITE_LOCK = asyncio.Lock()


# ── Client / Collection ────────────────────────────────────

def get_client() -> chromadb.PersistentClient:
    """
    Embedded ChromaDB — runs inside this process, persists to a Docker volume.
    No separate ChromaDB container needed.
    """
    global _CLIENT
    if _CLIENT is None:
        Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
        _CLIENT = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR,
            settings=chromadb.Settings(
                anonymized_telemetry=False,  # disable telemetry in prod
                allow_reset=False,           # prevent accidental full wipe
            ),
        )
    return _CLIENT


def get_embedding_fn() -> SentenceTransformerEmbeddingFunction:
    global _EMBEDDING_FN
    if _EMBEDDING_FN is None:
        _EMBEDDING_FN = SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)
    return _EMBEDDING_FN


def get_collection(name: str = DEFAULT_COLLECTION) -> Collection:
    """Get or create a named collection."""
    return get_client().get_or_create_collection(
        name=name,
        embedding_function=get_embedding_fn(),
        metadata={"hnsw:space": "cosine"},
    )


def list_collections() -> list[str]:
    return [c.name for c in get_client().list_collections()]


def delete_collection(name: str) -> None:
    get_client().delete_collection(name=name)


# ── Safe Write Operations ──────────────────────────────────

async def safe_upsert(
    collection: Collection,
    *,
    ids: list[str],
    documents: list[str],
    metadatas: list[dict] | None = None,
) -> None:
    """
    Safe upsert — acquires the write lock before writing.
    Concurrent upsert calls will queue up and execute one at a time.
    """
    async with _WRITE_LOCK:
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )


async def safe_delete(
    collection: Collection,
    *,
    ids: list[str],
) -> None:
    """
    Safe delete — acquires the write lock before deleting.
    """
    async with _WRITE_LOCK:
        collection.delete(ids=ids)
