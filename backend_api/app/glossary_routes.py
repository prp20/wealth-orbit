"""Public glossary chat API (definitions only; no auth or market reads)."""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .portfolio_backend import (
    answer_glossary_message,
    cached_glossary_terms,
    run_glossary_agent,
    sanitize_public_agent_payload,
)

logger = logging.getLogger("wealth_orbit.glossary")

router = APIRouter(prefix="/glossary", tags=["glossary"])

_MAX_MESSAGE_CHARS = 2000
_MAX_AGENT_MESSAGES = 20
_RATE_LIMIT_WINDOW_SECONDS = 60.0
_RATE_LIMIT_MAX_REQUESTS = 30

_rate_lock = Lock()
_rate_hits: dict[str, deque[float]] = defaultdict(deque)


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _enforce_rate_limit(request: Request) -> None:
    now = time.monotonic()
    key = _client_key(request)
    with _rate_lock:
        bucket = _rate_hits[key]
        while bucket and now - bucket[0] > _RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= _RATE_LIMIT_MAX_REQUESTS:
            raise HTTPException(status_code=429, detail="Too many glossary requests; try again shortly")
        bucket.append(now)


class GlossaryChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=_MAX_MESSAGE_CHARS)


class GlossaryAgentMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=_MAX_MESSAGE_CHARS)


class GlossaryAgentChatBody(BaseModel):
    messages: list[GlossaryAgentMessage] = Field(min_length=1, max_length=_MAX_AGENT_MESSAGES)


@router.post("/chat")
def glossary_chat(body: GlossaryChatBody, request: Request) -> dict:
    _enforce_rate_limit(request)
    try:
        return answer_glossary_message(body.message).as_dict()
    except Exception:
        logger.exception("glossary chat failed")
        raise HTTPException(status_code=500, detail="Glossary request failed") from None


@router.post("/agent/chat")
def glossary_agent_chat(body: GlossaryAgentChatBody, request: Request) -> dict:
    _enforce_rate_limit(request)
    try:
        payload = [item.model_dump() for item in body.messages]
        return sanitize_public_agent_payload(run_glossary_agent(payload))
    except Exception:
        logger.exception("glossary agent chat failed")
        raise HTTPException(status_code=500, detail="Glossary agent request failed") from None


@router.get("/terms")
def glossary_terms() -> list[dict[str, object]]:
    try:
        return [
            {"term": entry.term, "aliases": list(entry.aliases)}
            for entry in cached_glossary_terms()
        ]
    except Exception:
        logger.exception("glossary terms list failed")
        raise HTTPException(status_code=500, detail="Glossary terms unavailable") from None
