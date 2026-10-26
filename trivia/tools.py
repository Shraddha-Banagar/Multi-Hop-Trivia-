"""The action space available to the ReAct agent.

Three tools, one uniform interface:

``dictionary_lookup``  exact key/value lookup over the curated facts
``chroma_search``      top-k similarity search over the mock document index
``memory_lookup``      read a fact already discovered earlier in the session
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .kb import (
    ATTRIBUTES,
    CURATED_FACTS,
    ENTITY_TYPES,
    Fact,
    MockChromaCollection,
    build_chroma,
    build_dictionary,
    canonical,
    get_chroma,
    normalize,
)


# --------------------------------------------------------------------------


@dataclass
class Candidate:
    """A possible answer extracted from one or more retrieved documents."""

    value: str
    value_type: str
    side: str
    support: float = 0.0
    confidence: float = 0.0
    doc_ids: List[str] = field(default_factory=list)
    snippets: List[str] = field(default_factory=list)

    @property
    def votes(self) -> int:
        return len(self.doc_ids)


@dataclass
class RetrievedDoc:
    id: str
    text: str
    similarity: float
    metadata: Dict[str, Any]
    role: str = "noise"  # "candidate" | "noise"
    extracted_value: Optional[str] = None
    extracted_type: Optional[str] = None
    side: Optional[str] = None

    @property
    def is_decoy(self) -> bool:
        return bool(self.metadata.get("decoy"))

    @property
    def confidence(self) -> float:
        return float(self.metadata.get("confidence", 0.0))


@dataclass
class Observation:
    status: str  # "ok" | "not_found" | "error"
    value: Optional[str] = None
    value_type: Optional[str] = None
    side: Optional[str] = None
    message: str = ""
    candidates: List[Candidate] = field(default_factory=list)
    docs: List[RetrievedDoc] = field(default_factory=list)
    scanned: int = 0
    returned: int = 0
    noise: int = 0
    tool: str = ""
    source: str = ""
    query: str = ""
    confidence: float = 0.0
    selection_rule: str = ""
    doc_ids: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------


class SessionMemory:
    """Facts already established during the current session."""

    def __init__(self) -> None:
        self._facts: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def key(attribute: str, anchor: str) -> str:
        return f"{attribute}|{normalize(anchor)}"

    def get(self, attribute: str, anchor: str) -> Optional[Dict[str, Any]]:
        return self._facts.get(self.key(attribute, anchor))

    def put(
        self,
        attribute: str,
        anchor: str,
        value: str,
        value_type: str,
        tool: str,
        confidence: float,
        hop: int,
        source: str = "",
    ) -> None:
        self._facts[self.key(attribute, anchor)] = {
            "attribute": attribute,
            "anchor": anchor,
            "value": value,
            "value_type": value_type,
            "tool": tool,
            "confidence": confidence,
            "hop": hop,
            "source": source,
        }

    def as_list(self) -> List[Dict[str, Any]]:
        return list(self._facts.values())

    def clear(self) -> None:
        self._facts.clear()

    def __len__(self) -> int:
        return len(self._facts)


# --------------------------------------------------------------------------


def _type_ok(value_type: str, expect: Optional[Sequence[str]]) -> bool:
    if not expect:
        return True
    return value_type in set(expect)


class DictionaryTool:
    """Exact ``(attribute, anchor)`` key lookup - the high-precision baseline."""

    name = "dictionary_lookup"
    mode = "dictionary"

    def __init__(self) -> None:
        self.index = build_dictionary()
        self.facts: List[Fact] = list(CURATED_FACTS)

    def search(
        self,
        attribute: str,
        anchor: str,
        expect_type: Optional[Sequence[str]] = None,
        query: str = "",
        k: int = 4,
    ) -> Observation:
        anchor_norm = normalize(anchor)
        candidates: List[Candidate] = []
        for fact in self.facts:
            if fact.attribute != attribute:
                continue
            if normalize(fact.subject) == anchor_norm:
                side, value, vtype = "value", fact.value, fact.value_type
            elif normalize(fact.value) == anchor_norm:
                side, value, vtype = "subject", fact.subject, fact.subject_type
            else:
                continue
            if not _type_ok(vtype, expect_type):
                continue
            candidates.append(
                Candidate(
                    value=value,
                    value_type=vtype,
                    side=side,
                    support=fact.confidence,
                    confidence=fact.confidence,
                    doc_ids=[fact.id],
                    snippets=[fact.text],
                )
            )
        if not candidates:
            return Observation(
                status="not_found",
                message=(
                    f"No key '{attribute} | {anchor}' in the curated dictionary. "
                    "The lookup table does not contain this fact."
                ),
                tool=self.name,
                scanned=len(self.facts),
                source="Curated KB",
                query=f"{attribute} | {anchor}",
            )
        best = candidates[0]
        return Observation(
            status="ok",
            value=best.value,
            value_type=best.value_type,
            side=best.side,
            message=f"{attribute}({anchor}) = {best.value}",
            candidates=candidates,
            scanned=len(self.facts),
            returned=len(candidates),
            tool=self.name,
            source=best.snippets[0],
            query=f"{attribute} | {anchor}",
            confidence=best.confidence,
            selection_rule="exact key match (k = 1 by construction)",
            doc_ids=list(best.doc_ids),
        )


class ChromaTool:
    """Similarity search over the mock ChromaDB collection."""

    name = "chroma_search"
    mode = "chroma"

    def __init__(self, collection: Optional[MockChromaCollection] = None) -> None:
        # ``get_chroma`` returns the cached, disk-backed collection, so the
        # index is embedded once per process instead of once per tool call.
        self.collection = collection if collection is not None else get_chroma()

    def search(
        self,
        attribute: str,
        anchor: str,
        expect_type: Optional[Sequence[str]] = None,
        query: str = "",
        k: int = 4,
    ) -> Observation:
        query = query or ATTRIBUTES.get(attribute, {}).get("query", "{anchor}").format(anchor=anchor)
        result = self.collection.query([query], n_results=k)
        anchor_norm = normalize(anchor)
        docs: List[RetrievedDoc] = []
        candidates: Dict[str, Candidate] = {}

        for doc_id, text, meta, sim in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["similarities"][0],
        ):
            role = "noise"
            value: Optional[str] = None
            vtype: Optional[str] = None
            side: Optional[str] = None
            if meta.get("attribute") == attribute:
                if normalize(meta.get("subject", "")) == anchor_norm:
                    value, vtype, side = meta["value"], meta["value_type"], "value"
                elif normalize(meta.get("value", "")) == anchor_norm:
                    value, vtype, side = meta["subject"], meta["subject_type"], "subject"
            if value is not None and _type_ok(vtype or "", expect_type):
                role = "candidate"
                cand = candidates.setdefault(
                    value,
                    Candidate(value=value, value_type=vtype or "", side=side or "value"),
                )
                cand.doc_ids.append(doc_id)
                cand.snippets.append(text)
                cand.support += float(meta.get("confidence", 0.0)) * float(sim)
                cand.confidence = max(cand.confidence, float(meta.get("confidence", 0.0)))
            docs.append(
                RetrievedDoc(
                    id=doc_id,
                    text=text,
                    similarity=float(sim),
                    metadata=meta,
                    role=role,
                    extracted_value=value,
                    extracted_type=vtype,
                    side=side,
                )
            )

        noise = sum(1 for d in docs if d.role == "noise")
        if not candidates:
            return Observation(
                status="not_found",
                message=(
                    f"No document in the top-{k} context for '{query}' carries the fact "
                    f"'{attribute}' of '{anchor}'."
                ),
                docs=docs,
                scanned=self.collection.count(),
                returned=len(docs),
                noise=noise,
                tool=self.name,
                source=f"query: {query}",
                query=query,
            )

        ranked = sorted(candidates.values(), key=lambda c: -c.support)
        top_doc = next((d for d in docs if d.role == "candidate"), None)
        best = ranked[0]
        return Observation(
            status="ok",
            value=top_doc.extracted_value if top_doc else best.value,
            value_type=top_doc.extracted_type if top_doc else best.value_type,
            side=top_doc.side if top_doc else best.side,
            message=f"{attribute}({anchor}) = {top_doc.extracted_value if top_doc else best.value}",
            candidates=ranked,
            docs=docs,
            scanned=self.collection.count(),
            returned=len(docs),
            noise=noise,
            tool=self.name,
            source=f"query: {query}",
            query=query,
            confidence=top_doc.confidence if top_doc else best.confidence,
            selection_rule="ranked by confidence x similarity",
            doc_ids=[top_doc.id] if top_doc else list(best.doc_ids),
        )


class MemoryTool:
    """Reads a fact that was already established earlier in this session."""

    name = "memory_lookup"
    mode = "memory"

    def __init__(self, memory: SessionMemory) -> None:
        self.memory = memory

    def search(
        self,
        attribute: str,
        anchor: str,
        expect_type: Optional[Sequence[str]] = None,
        query: str = "",
        k: int = 4,
    ) -> Observation:
        hit = self.memory.get(attribute, anchor)
        if not hit:
            return Observation(
                status="not_found",
                message=f"Session memory has no entry for '{attribute} | {anchor}'.",
                tool=self.name,
                query=f"{attribute} | {anchor}",
            )
        return Observation(
            status="ok",
            value=hit["value"],
            value_type=hit["value_type"],
            side="value",
            message=f"cached: {attribute}({anchor}) = {hit['value']} (hop {hit['hop']})",
            source=f"session memory, stored during hop {hit['hop']}",
            tool=self.name,
            confidence=hit.get("confidence", 1.0),
            selection_rule="session cache hit",
            doc_ids=[f"memory::{hit['attribute']}|{normalize(hit['anchor'])}"],
        )


# --------------------------------------------------------------------------


class ToolRouter:
    """Dispatches tool calls for the currently selected retrieval mode."""

    def __init__(self, mode: str = "dictionary", k: int = 4) -> None:
        self.mode = mode
        self.k = k
        self.dictionary = DictionaryTool()
        self.chroma = ChromaTool()
        self.memory = SessionMemory()
        self.memory_tool = MemoryTool(self.memory)
        self.calls: List[Dict[str, Any]] = []

    # -- helpers -----------------------------------------------------------
    @property
    def active(self) -> Any:
        return self.chroma if self.mode == "chroma" else self.dictionary

    @property
    def active_name(self) -> str:
        return "chroma_search" if self.mode == "chroma" else "dictionary_lookup"

    def search(
        self,
        attribute: str,
        anchor: str,
        expect_type: Optional[Sequence[str]] = None,
        query: str = "",
        attempt: int = 0,
        k: Optional[int] = None,
    ) -> Observation:
        effective_query = self._query_for(attribute, anchor, query, attempt)
        obs = self.active.search(
            attribute=attribute,
            anchor=anchor,
            expect_type=expect_type,
            query=effective_query,
            k=k if k is not None else self.k,
        )
        obs.tool = self.active_name
        self.calls.append(
            {
                "tool": self.active_name,
                "mode": self.mode,
                "k": self.k,
                "attribute": attribute,
                "anchor": anchor,
                "query": effective_query,
                "status": obs.status,
                "value": obs.value,
                "returned": obs.returned,
                "noise": obs.noise,
                "scanned": obs.scanned,
            }
        )
        return obs

    def _query_for(self, attribute: str, anchor: str, query: str, attempt: int) -> str:
        if self.mode != "chroma":
            return query
        if attempt == 0:
            return query or ATTRIBUTES.get(attribute, {}).get("query", "{anchor}").format(anchor=anchor)
        if attempt == 1:
            return f"{anchor} {attribute}".strip()
        return f"{anchor}".strip()

    def remember(self, attribute: str, anchor: str, obs: Observation, hop: int) -> None:
        if obs.status == "ok" and obs.value:
            self.memory.put(
                attribute=attribute,
                anchor=anchor,
                value=obs.value,
                value_type=obs.value_type or "",
                tool=obs.tool,
                confidence=obs.confidence,
                hop=hop,
                source=obs.source,
            )
