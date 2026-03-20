# Copyright (c) 2026 Surinder Singh (https://github.com/surinderlohat)
# Licensed under the MIT License. See LICENSE file in the project root.
from __future__ import annotations

import os

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import get_collection, list_collections
from app.log_buffer import get_logs
from app.logger import get_logger
from app.memory import MEMORY_LIMIT_MB, MEMORY_WARN_MB, get_memory_mb
from app.schemas import SingleUpsertRequest

logger = get_logger(__name__)
router = APIRouter()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SESSION_TOKEN  = "searchkit_admin_session"

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "../templates"))


# ── Session auth ───────────────────────────────────────────

def verify_admin_session(session: str | None = Cookie(default=None, alias=SESSION_TOKEN)) -> str:
    """Verify admin session cookie."""
    if not ADMIN_PASSWORD:
        return "no-auth"
    if session != ADMIN_PASSWORD:
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    return session


# ── Login ──────────────────────────────────────────────────

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


# ── API endpoints used by dashboard JS ────────────────────

@router.get("/api/stats", include_in_schema=False)
async def stats(session: str = Depends(verify_admin_session)):
    names = list_collections()
    collections = []
    for name in names:
        col = get_collection(name)
        collections.append({"name": name, "count": col.count()})
    return {
        "collections": collections,
        "memory_mb":       round(get_memory_mb(), 1),
        "memory_warn_mb":  MEMORY_WARN_MB,
        "memory_limit_mb": MEMORY_LIMIT_MB,
    }


@router.get("/api/logs", include_in_schema=False)
async def logs(session: str = Depends(verify_admin_session)):
    return {"logs": get_logs()}


@router.post("/api/search", include_in_schema=False)
async def admin_search(request: Request, session: str = Depends(verify_admin_session)):
    body = await request.json()
    query      = body.get("query", "")
    collection = body.get("collection", "default")
    top_k      = int(body.get("top_k", 10))

    col = get_collection(collection)
    if col.count() == 0:
        return {"results": []}

    results = col.query(
        query_texts=[query],
        n_results=min(top_k, col.count()),
        include=["documents", "metadatas", "distances"],
    )
    return {
        "results": [
            {
                "id":       results["ids"][0][i],
                "text":     results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": round(results["distances"][0][i], 4),
            }
            for i in range(len(results["ids"][0]))
        ]
    }


@router.get("/api/documents", include_in_schema=False)
async def list_documents(
    collection: str = "default",
    limit: int = 50,
    session: str = Depends(verify_admin_session),
):
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


@router.delete("/api/documents/{doc_id}", include_in_schema=False)
async def delete_document(
    doc_id: str,
    collection: str = "default",
    session: str = Depends(verify_admin_session),
):
    col = get_collection(collection)
    col.delete(ids=[doc_id])
    logger.warning(f"Admin deleted document '{doc_id}' from '{collection}'")
    return {"status": "ok", "message": f"Deleted '{doc_id}'"}
