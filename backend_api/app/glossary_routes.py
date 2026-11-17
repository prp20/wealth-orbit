"""Public glossary chat API (definitions only; no auth or market reads)."""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .portfolio_backend import (
    answer_glossary_message,
    cached_glossary_terms,
    run_glossary_agent,
)

logger = logging.getLogger("wealth_orbit.glossary")

router = APIRouter(prefix="/glossary", tags=["glossary"])


class GlossaryChatBody(BaseModel):
    message: str = Field(min_length=1)


class GlossaryAgentMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class GlossaryAgentChatBody(BaseModel):
    messages: list[GlossaryAgentMessage] = Field(min_length=1)


@router.post("/chat")
def glossary_chat(body: GlossaryChatBody) -> dict:
    try:
        return answer_glossary_message(body.message).as_dict()
    except Exception:
        logger.exception("glossary chat failed")
        raise HTTPException(status_code=500, detail="Glossary request failed") from None


@router.post("/agent/chat")
def glossary_agent_chat(body: GlossaryAgentChatBody) -> dict:
    try:
        payload = [item.model_dump() for item in body.messages]
        return run_glossary_agent(payload)
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