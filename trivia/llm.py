"""A deterministic mock LLM.

The *control flow* of the agent is real (see ``researcher.py``): the LLM
decides what to do next and the code executes it. What is mocked is the
language generation - a policy module that produces the Thought strings and
picks the value out of a retrieved context window.

The selection policy is the interesting part:

``exact``      the curated dictionary answered - take the key's value.
``greedy``     no majority in the retrieved context - take the value of the
               highest ranked passage (this is what a naive RAG agent does and
               it is how a bad document poisons the chain).
``majority``   several passages agree - take the agreed value (redundancy in
               the index repairs a poisoned hop).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .tools import Observation


HALLUCINATIONS = {
    "mayor": ("Michael Muller", "Michael Muller was elected mayor of the city in 2014."),
    "capital": ("Lyon", "Lyon is the capital of the country and its largest city."),
    "largest_city": ("Melbourne", "Melbourne is the largest city of the country by population."),
    "director": ("Ridley Scott", "Ridley Scott directed the blockbuster film."),
    "birthplace": ("Santa Monica", "The filmmaker was born in Santa Monica, California."),
    "location": ("Japan", "The landmark is located in Japan."),
    "country": ("Japan", "The city lies in the country of Japan."),
    "nationality": ("British", "The director is a British filmmaker."),
}


@dataclass
class Selection:
    value: Optional[str]
    rule: str
    votes: Dict[str, int] = None
    runner_up: Optional[str] = None

    def __post_init__(self) -> None:
        if self.votes is None:
            self.votes = {}


class MockLLM:
    """Mocked LLM: emits thoughts and reads the retrieved context."""

    def __init__(self, allow_hallucination: bool = False, mode: str = "dictionary") -> None:
        self.allow_hallucination = allow_hallucination
        self.mode = mode

    # -- thought generation ------------------------------------------------
    def thought_for(self, hop, attempt: int, anchor: str) -> str:
        verb = {
            "capital": "find the capital of",
            "mayor": "find the mayor of",
            "largest_city": "find the largest city of",
            "director": "find the director of",
            "birthplace": "find the birthplace of",
            "location": "find the country where",
            "country": "find the country of",
            "nationality": "find the nationality of",
        }.get(hop.attribute, f"look up {hop.attribute} of")
        if attempt == 0:
            return (
                f"Hop {hop.index}: I need to {verb} {anchor}. "
                f"I will use the {self._tool_label()} with the query "
                f"\"{self._query_label(hop, anchor)}\"."
            )
        return (
            f"Hop {hop.index}: the first attempt did not surface the fact \"{hop.attribute}\" "
            f"of {anchor}. I will broaden the query to \"{self._query_label(hop, anchor, attempt)}\" "
            "and look through more of the retrieved context."
        )

    def thought_bridge(self, hop, value: str, next_hop) -> str:
        return (
            f"Hop {hop.index} resolved: {hop.attribute}({hop.anchor}) = {value}. "
            f"That gives me the bridge entity for hop {next_hop.index} - now I need to "
            f"{'find the ' + next_hop.attribute.replace('_', ' ') + ' of'} {value}."
        )

    def thought_finish(self, answer: str, chain: Sequence[str]) -> str:
        return (
            f"Every hop is resolved and the chain {', '.join(chain)} is internally consistent. "
            f"The question asks for the end of the chain, so I can answer: {answer}."
        )

    def thought_missing(self, hop, anchor: str) -> str:
        return (
            f"Hop {hop.index} is unresolved: the knowledge base does not contain "
            f"\"{hop.attribute}\" of {anchor}. Continuing would require inventing the fact, "
            "so I stop and report the missing information instead."
        )

    def thought_hallucinate(self, hop, anchor: str, value: str, snippet: str) -> str:
        return (
            f"Hop {hop.index} is unresolved. The retrieved context does not contain "
            f"\"{hop.attribute}\" of {anchor}, but I will answer from my own knowledge: "
            f"{snippet}"
        )

    def _tool_label(self) -> str:
        return "Chroma RAG index" if self.mode == "chroma" else "curated dictionary"

    def _query_label(self, hop, anchor: str, attempt: int = 0) -> str:
        from .kb import ATTRIBUTES

        if attempt >= 1:
            return f"{anchor} {hop.attribute}".strip()
        template = ATTRIBUTES.get(hop.attribute, {}).get("query", "{anchor}")
        return template.format(anchor=anchor)

    # -- context reading ---------------------------------------------------
    def select(self, obs: Observation) -> Selection:
        """Pick the answer out of a retrieved context window."""
        if obs.status != "ok":
            return Selection(None, "no supporting passage found", {})

        if obs.tool == "dictionary_lookup":
            if not obs.candidates:
                return Selection(None, "no supporting passage found", {})
            return Selection(
                obs.candidates[0].value,
                "exact key match on the curated dictionary (k = 1 by construction)",
                {obs.candidates[0].value: 1},
            )

        passages = [d for d in obs.docs if d.role == "candidate" and d.extracted_value]
        if not passages:
            return Selection(None, "no supporting passage found", {})

        votes: Dict[str, int] = {}
        for p in passages:
            votes[p.extracted_value] = votes.get(p.extracted_value, 0) + 1
        ranked = sorted(votes.items(), key=lambda kv: (-kv[1], -max(
            p.similarity for p in passages if p.extracted_value == kv[0])))
        best_value, best_votes = ranked[0]
        runner_up = ranked[1][0] if len(ranked) > 1 else None

        if best_votes >= 2:
            return Selection(
                best_value,
                f"majority vote: {best_votes} of {len(passages)} retrieved passages agree",
                votes,
                runner_up,
            )
        return Selection(
            passages[0].extracted_value,
            "top-ranked passage (no majority available in the context window)",
            votes,
            runner_up,
        )

    # -- unsafe mode -------------------------------------------------------
    def hallucinate(self, hop, anchor: str) -> Tuple[str, str]:
        value, snippet = HALLUCINATIONS.get(
            hop.attribute, ("Unknown", f"I believe the {hop.attribute} of {anchor} is well known.")
        )
        return value, snippet
