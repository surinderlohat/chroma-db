# Copyright (c) 2025 Surinder Singh (https://github.com/surinderlohat)
# Licensed under the MIT License. See LICENSE file in the project root.
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import chromadb
from chromadb import Collection
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from app.logger import get_logger

logger = get_logger(__name__)

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "/app/chromadb")
DEFAULT_COLLECTION = os.getenv("DEFAULT_COLLECTION", "default")


def _resolve_device() -> str:
    """
    Resolve the embedding device to a valid PyTorch device string.
    'auto' is NOT a valid torch device — we detect GPU availability ourselves.

    EMBEDDING_DEVICE=auto  → detects cuda if available, falls back to cpu
    EMBEDDING_DEVICE=cpu   → always cpu
    EMBEDDING_DEVICE=cuda  → always cuda (will error if no GPU present)
    """
    requested = os.getenv("EMBEDDING_DEVICE", "auto").lower()
    if requested == "auto":
        try:
            import torch

            resolved = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            resolved = "cpu"
        logger.info(f"EMBEDDING_DEVICE=auto resolved to '{resolved}'")
        return resolved
    return requested  # cpu / cuda passed explicitly — use as-is


EMBEDDING_DEVICE = _resolve_device()

_CLIENT: chromadb.PersistentClient | None = None
_EMBEDDING_FN: SentenceTransformerEmbeddingFunction | None = None

# Single async lock — serializes all write operations (upsert / delete)
_WRITE_LOCK = asyncio.Lock()


# ── Client / Collection ────────────────────────────────────


def get_client() -> chromadb.PersistentClient:
    global _CLIENT
    if _CLIENT is None:
        Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
        logger.debug(f"Connecting to ChromaDB at '{CHROMA_PERSIST_DIR}'")
        _CLIENT = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR,
            settings=chromadb.Settings(
                anonymized_telemetry=False,
                allow_reset=False,
            ),
        )
        logger.info("ChromaDB PersistentClient initialized.")
    return _CLIENT


def get_embedding_fn() -> SentenceTransformerEmbeddingFunction:
    global _EMBEDDING_FN
    if _EMBEDDING_FN is None:
        logger.info(f"Loading embedding model '{MODEL_NAME}' on device '{EMBEDDING_DEVICE}'...")
        _EMBEDDING_FN = SentenceTransformerEmbeddingFunction(
            model_name=MODEL_NAME,
            device=EMBEDDING_DEVICE,
        )
        logger.info("Embedding model loaded successfully.")
    return _EMBEDDING_FN


def get_collection(name: str = DEFAULT_COLLECTION) -> Collection:
    logger.debug(f"Fetching collection '{name}'")
    return get_client().get_or_create_collection(
        name=name,
        embedding_function=get_embedding_fn(),
        metadata={"hnsw:space": "cosine"},
    )


def list_collections() -> list[str]:
    names = [c.name for c in get_client().list_collections()]
    logger.debug(f"Listed {len(names)} collections")
    return names


def delete_collection(name: str) -> None:
    logger.warning(f"Deleting collection '{name}'")
    get_client().delete_collection(name=name)
    logger.info(f"Collection '{name}' deleted.")


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
    logger.debug(f"Upserting {len(ids)} documents into '{collection.name}'")
    async with _WRITE_LOCK:
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
    logger.debug(f"Upsert complete for {len(ids)} documents.")


async def safe_delete(
    collection: Collection,
    *,
    ids: list[str],
) -> None:
    """
    Safe delete — acquires the write lock before deleting.
    """
    logger.debug(f"Deleting {len(ids)} documents from '{collection.name}'")
    async with _WRITE_LOCK:
        collection.delete(ids=ids)
    logger.debug(f"Delete complete for {len(ids)} documents.")
