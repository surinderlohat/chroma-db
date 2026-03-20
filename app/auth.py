# Copyright (c) 2026 Surinder Singh (https://github.com/surinderlohat)
# Licensed under the MIT License. See LICENSE file in the project root.
from __future__ import annotations

import os

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.logger import get_logger

logger = get_logger(__name__)

# Read API key from environment — set via docker-compose
API_KEY = os.getenv("API_KEY", "")
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    Validates the API key from the X-API-Key request header.

    - If API_KEY env var is not set → auth is disabled (open access)
    - If API_KEY is set → key must match exactly or request is rejected
    """
    # Auth disabled — no API_KEY configured
    if not API_KEY:
        logger.debug("API key auth disabled — no API_KEY configured")
        return ""

    if api_key == API_KEY:
        logger.debug("API key verified successfully")
        return api_key

    logger.warning("Unauthorized request — invalid or missing API key")
    raise HTTPException(
        status_code=401,
        detail="Invalid or missing API key. Pass it via the X-API-Key header.",
    )
