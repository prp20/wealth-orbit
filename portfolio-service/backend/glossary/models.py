"""Structured glossary chat results (retrieval-only, no LLM)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class GlossaryResultKind(str, Enum):
    MATCH = "match"
    REFUSAL = "refusal"
    UNKNOWN = "unknown"


class RefusalCategory(str, Enum):
    ADVICE = "advice"
    DUMP = "dump"


@dataclass(frozen=True)
class GlossarySource:
    module: int
    chapter: str
    url: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> GlossarySource:
        return cls(
            module=int(raw["module"]),
            chapter=str(raw["chapter"]),
            url=str(raw["url"]),
        )


@dataclass(frozen=True)
class GlossaryTerm:
    term: str
    aliases: tuple[str, ...]
    definition: str
    sources: tuple[GlossarySource, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> GlossaryTerm:
        aliases = tuple(str(a) for a in (raw.get("aliases") or []))
        sources = tuple(GlossarySource.from_dict(s) for s in (raw.get("sources") or []))
        return cls(
            term=str(raw["term"]),
            aliases=aliases,
            definition=str(raw["definition"]),
            sources=sources,
        )


@dataclass(frozen=True)
class GlossaryResult:
    kind: GlossaryResultKind
    term: str | None = None
    definition: str | None = None
    sources: tuple[GlossarySource, ...] = ()
    refusal_reason: str | None = None
    refusal_category: RefusalCategory | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"kind": self.kind.value}
        if self.kind is GlossaryResultKind.MATCH:
            payload["term"] = self.term
            payload["definition"] = self.definition
            payload["sources"] = [
                {"module": s.module, "chapter": s.chapter, "url": s.url} for s in self.sources
            ]
        elif self.kind is GlossaryResultKind.REFUSAL:
            payload["refusal_reason"] = self.refusal_reason
            payload["refusal_category"] = (
                self.refusal_category.value if self.refusal_category else None
            )
        return payload