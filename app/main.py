# Copyright (c) 2026 Surinder Singh (https://github.com/surinderlohat)
# Licensed under the MIT License. See LICENSE file in the project root.
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse

from app.auth import verify_api_key
from app.db import get_collection
from app.log_buffer import attach_buffer_handler
from app.logger import get_logger
from app.routers import admin, collections, documents, health, search

logger = get_logger(__name__)

_API_KEY_SET = bool(os.getenv("API_KEY", ""))


@asynccontextmanager
async def lifespan(app: FastAPI):
    attach_buffer_handler()  # capture logs into in-memory buffer for admin dashboard
    logger.info("Initializing embedded ChromaDB...")
    get_collection()
    logger.info("ChromaDB ready (embedded mode).")
    if _API_KEY_SET:
        logger.info("API key authentication enabled.")
    else:
        logger.warning("API key auth disabled — set API_KEY env var to enable.")
    yield
    logger.info("Shutting down SearchKit.")


app = FastAPI(
    title="SearchKit",
    description="Plug-in semantic search for any stack — one container, zero config, production ready.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Public endpoints ───────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    """Root — redirects to Swagger UI."""
    return RedirectResponse(url="/docs")


@app.get("/docs", include_in_schema=False)
async def swagger_ui():
    """Swagger UI — always public. API key entered via Authorize button."""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="SearchKit",
        swagger_ui_parameters={
            "persistAuthorization": True,  # remembers key across page refreshes
        },
    )


@app.get("/openapi.json", include_in_schema=False)
async def openapi_schema():
    """
    OpenAPI schema — public so Swagger UI can load it without auth.
    Injects ApiKeyAuth security scheme so Swagger UI shows the Authorize
    button and sends X-API-Key header on every Try it out request.
    """
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Inject API key security scheme into the schema manually
    # get_openapi() does not support openapi_extra directly
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
    }
    schema["security"] = [{"ApiKeyAuth": []}]

    return schema


# ── Auth-protected routers ─────────────────────────────────
# All API endpoints require a valid X-API-Key header

_auth = Depends(verify_api_key)

app.include_router(health.router, tags=["Health"], dependencies=[_auth])
app.include_router(collections.router, prefix="/collections", tags=["Collections"], dependencies=[_auth])
app.include_router(documents.router, prefix="/documents", tags=["Documents"], dependencies=[_auth])
app.include_router(search.router, prefix="/search", tags=["Search"], dependencies=[_auth])
app.include_router(admin.router, prefix="/admin", include_in_schema=False)
