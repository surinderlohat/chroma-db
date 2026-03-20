# Copyright (c) 2026 Surinder Singh (https://github.com/surinderlohat)
# Licensed under the MIT License. See LICENSE file in the project root.
from __future__ import annotations

import asyncio
import csv
import io
import json
import os

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemLoader, Environment

from app.db import delete_collection, get_collection, list_collections, safe_upsert
from app.log_buffer import get_logs
from app.logger import get_logger
from app.memory import MEMORY_LIMIT_MB, MEMORY_WARN_MB, get_memory_mb

logger = get_logger(__name__)
router = APIRouter()

ADMIN_PASSWORD  = os.getenv("ADMIN_PASSWORD", "")
SESSION_TOKEN   = "searchkit_admin_session"

# Use FileSystemLoader so Jinja2 resolves subdirectory includes like
# partials/page_overview.html correctly
_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "../templates")
templates = Jinja2Templates(env=Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=True,
))


# ── Session auth ───────────────────────────────────────────

def verify_admin_session(
    session: str | None = Cookie(default=None, alias=SESSION_TOKEN),
) -> str:
    if not ADMIN_PASSWORD:
        return "no-auth"
    if session != ADMIN_PASSWORD:
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    return session


# ── Login / Logout ─────────────────────────────────────────

@router.get("/login", include_in_schema=False)
async def login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})


@router.post("/login", include_in_schema=False)
async def login(request: Request):
    form = await request.form()
    password = form.get("password", "")
    if password == ADMIN_PASSWORD:
        response = RedirectResponse(url="/admin", status_code=302)
        response.set_cookie(SESSION_TOKEN, password, httponly=True, samesite="strict")
        logger.info("Admin login successful")
        return response
    logger.warning("Admin login failed — wrong password")
    return templates.TemplateResponse(
        "admin_login.html",
        {"request": request, "error": "Invalid password"},
        status_code=401,
    )


@router.get("/logout", include_in_schema=False)
async def logout():
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie(SESSION_TOKEN)
    return response


# ── Dashboard ──────────────────────────────────────────────

@router.get("", include_in_schema=False)
async def dashboard(request: Request, session: str = Depends(verify_admin_session)):
    return templates.TemplateResponse("admin_dashboard.html", {"request": request})


# ── Admin-only endpoints (no equivalent in public API) ────

@router.get("/api/stats", include_in_schema=False)
async def stats(session: str = Depends(verify_admin_session)):
    """Memory stats + collection summary — admin only, not in public API."""
    names = list_collections()
    collections = [
        {"name": name, "count": get_collection(name).count()}
        for name in names
    ]
    return {
        "collections":     collections,
        "memory_mb":       round(get_memory_mb(), 1),
        "memory_warn_mb":  MEMORY_WARN_MB,
        "memory_limit_mb": MEMORY_LIMIT_MB,
    }


@router.get("/api/documents/browse", include_in_schema=False)
async def browse_documents(
    collection: str = "default",
    limit: int = 50,
    session: str = Depends(verify_admin_session),
):
    """
    Browse all documents in a collection — admin only.
    The public API has no browse endpoint, only search.
    """
    col = get_collection(collection)
    results = col.get(limit=limit, include=["documents", "metadatas"])
    return {
        "documents": [
            {
                "id":       results["ids"][i],
                "text":     results["documents"][i],
                "metadata": results["metadatas"][i] if results["metadatas"] else {},
            }
            for i in range(len(results["ids"]))
        ],
        "total": col.count(),
    }


@router.post("/api/csv/preview", include_in_schema=False)
async def csv_preview(
    request: Request,
    session: str = Depends(verify_admin_session),
):
    """Read first 5 rows of uploaded CSV — admin only."""
    form = await request.form()
    file = form.get("file")
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    columns = reader.fieldnames or []
    rows = []
    for i, row in enumerate(reader):
        if i >= 5:
            break
        rows.append(dict(row))

    return {"columns": list(columns), "preview": rows}


@router.post("/api/csv/import", include_in_schema=False)
async def csv_import(
    request: Request,
    session: str = Depends(verify_admin_session),
):
    """
    SSE — imports CSV in batches, streams progress.
    Uses safe_upsert from db.py — same as public upsert endpoint.
    """
    form        = await request.form()
    file        = form.get("file")
    collection  = form.get("collection", "default")
    id_field    = form.get("id_field", "")
    text_fields = [f.strip() for f in form.get("text_fields", "").split(",") if f.strip()]
    batch_size  = int(form.get("batch_size", "200"))

    if not id_field:
        raise HTTPException(status_code=422, detail="id_field is required")
    if not text_fields:
        raise HTTPException(status_code=422, detail="text_fields is required")

    content = await file.read()
    try:
        text_content = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text_content = content.decode("latin-1")

    async def progress_stream():
        rows     = list(csv.DictReader(io.StringIO(text_content)))
        total    = len(rows)
        col      = get_collection(collection)
        imported = 0
        skipped  = 0

        yield f"data: {json.dumps({'type': 'start', 'total': total})}\n\n"

        for i in range(0, total, batch_size):
            batch = rows[i : i + batch_size]
            ids, texts, metas = [], [], []

            for row in batch:
                doc_id = str(row.get(id_field, "")).strip()
                text   = " ".join(
                    str(row.get(f, "")).strip()
                    for f in text_fields if row.get(f, "").strip()
                )
                if not doc_id or not text:
                    skipped += 1
                    continue
                meta = {k: v for k, v in row.items() if k != id_field and k not in text_fields and v}
                ids.append(doc_id)
                texts.append(text)
                metas.append(meta)

            if ids:
                await safe_upsert(col, ids=ids, documents=texts, metadatas=metas)
                imported += len(ids)

            progress = round(((i + len(batch)) / total) * 100)
            yield f"data: {json.dumps({'type': 'progress', 'progress': progress, 'imported': imported, 'skipped': skipped})}\n\n"
            await asyncio.sleep(0)

        logger.info(f"CSV import — {imported} imported, {skipped} skipped into '{collection}'")
        yield f"data: {json.dumps({'type': 'done', 'imported': imported, 'skipped': skipped, 'total': col.count()})}\n\n"

    return StreamingResponse(
        progress_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Live Logs SSE ──────────────────────────────────────────

@router.get("/api/logs/stream", include_in_schema=False)
async def logs_stream(session: str = Depends(verify_admin_session)):
    async def event_generator():
        last_count = 0
        while True:
            logs_asc = list(reversed(get_logs()))
            if len(logs_asc) > last_count:
                for line in logs_asc[last_count:]:
                    yield f"data: {json.dumps(line)}\n\n"
                last_count = len(logs_asc)
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
