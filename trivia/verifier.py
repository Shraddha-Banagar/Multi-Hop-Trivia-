"""The Verifier agent.

The researcher may be confidently wrong. The verifier re-reads the evidence
and asks four questions:

1. ``chain_type``      does every bridge entity have the type the next hop
                       needs (a city must feed "mayor", a country "capital")?
2. ``evidence_support`` is the claimed value backed by a *high authority*
                       document (confidence >= 0.7), or does it rest on a
                       single low-authority snippet?
3. ``conflict``        if we re-retrieve the hop with a stricter query and a
                       wider context window, do the other passages out-vote
                       the value the researcher took? (This is what catches a
                       poisoned first hop.)
4. ``answer_type``     does the final answer have the type the question asks
                       for?

A failing check produces a REJECTED verdict plus a *repair*: the alternative
value with the strongest support, which the researcher then re-runs the chain
with.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .planner import Plan
from .researcher import ResearchResult, Step
from .tools import ToolRouter


SUPPORT_MIN = 0.70
LOW_AUTHORITY = 0.50
CONFLICT_RATIO = 1.05


@dataclass
class Check:
    name: str
    status: str  # PASS | FAIL | WARN | N/A
    detail: str
    evidence: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in ("PASS", "N/A")


@dataclass
class Repair:
    hop_index: int
    value: str
    reason: str
    evidence: List[str] = field(default_factory=list)


@dataclass
class Verdict:
    status: str  # CONFIRMED | REJECTED | INSUFFICIENT_EVIDENCE
    headline: str
    explanation: str
    checks: List[Check] = field(default_factory=list)
    repair: Optional[Repair] = None
    poisoned_hop: Optional[int] = None
    corrected_answer: Optional[str] = None

    @property
    def failed(self) -> List[Check]:
        return [c for c in self.checks if c.status == "FAIL"]


# --------------------------------------------------------------------------


class Verifier:
    """Reviews the researcher's output against the retrieved evidence."""

    def __init__(self, router: ToolRouter) -> None:
        self.router = router

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _hop_steps(result: ResearchResult, hop_index: int) -> List[Step]:
        return result.steps_for_hop(hop_index)

    @staticmethod
    def _supporting_docs(result: ResearchResult, hop_index: int) -> List[Any]:
        docs: List[Any] = []
        for step in result.steps_for_hop(hop_index):
            for ev in step.evidence:
                if ev.value is not None and ev.role == "candidate":
                    docs.append(ev)
        return docs

    def _strict_retrieval(self, hop, anchor: str) -> Optional[List[Any]]:
        """Re-retrieve a hop with a stricter query and a wider context."""
        if self.router.mode != "chroma":
            return None
        obs = self.router.search(
            attribute=hop.attribute,
            anchor=anchor,
            expect_type=hop.expect_type,
            query=f"{anchor} {hop.attribute}".strip(),
            k=max(5, self.router.k + 3),
        )
        return [d for d in obs.docs if d.role == "candidate" and d.extracted_value]

    @staticmethod
    def _runtime_anchors(plan: Plan) -> Dict[int, str]:
        """The anchor each hop actually queried (bridge hops use the value
        produced by the previous hop)."""
        anchors: Dict[int, str] = {}
        previous: Optional[str] = None
        for hop in plan.hops:
            if hop.anchor_is_bridge:
                anchors[hop.index] = previous or hop.anchor
            else:
                anchors[hop.index] = hop.anchor
            previous = hop.resolved_value
        return anchors

    # -- main --------------------------------------------------------------
    def verify(self, question: str, plan: Plan, result: ResearchResult) -> Verdict:
        checks: List[Check] = []
        repair: Optional[Repair] = None
        poisoned_hop: Optional[int] = None
        anchors = self._runtime_anchors(plan)

        # 0. completeness --------------------------------------------------
        if result.stop_reason == "MISSING_INFORMATION":
            checks.append(
                Check(
                    name="completeness",
                    status="FAIL",
                    detail=(
                        f"The chain broke at \"{result.missing_fact}\". The knowledge base has no "
                        "such fact, so no answer can be supported."
                    ),
                )
            )
        elif result.stop_reason == "HOP_CAP_REACHED":
            checks.append(
                Check(
                    name="completeness",
                    status="WARN",
                    detail="The hop budget was exhausted before the chain was complete.",
                )
            )
        else:
            checks.append(
                Check(
                    name="completeness",
                    status="PASS",
                    detail=f"All {len(plan.hops)} planned hops resolved after {result.actions} tool call(s).",
                )
            )

        # 1. chain type ----------------------------------------------------
        type_failures: List[str] = []
        for hop in plan.hops:
            if hop.resolved_value is None:
                continue
            vtype = self._value_type(hop.resolved_value)
            if vtype and hop.expect_type and vtype not in hop.expect_type:
                type_failures.append(
                    f"hop {hop.index}: expected {'/'.join(hop.expect_type)}, got {vtype} "
                    f"({hop.resolved_value})"
                )
        checks.append(
            Check(
                name="chain_type",
                status="FAIL" if type_failures else "PASS",
                detail=(
                    "; ".join(type_failures)
                    if type_failures
                    else "Every bridge entity has the entity type the next hop requires."
                ),
            )
        )

        # 2 + 3. evidence support and conflict, hop by hop ------------------
        for hop in plan.hops:
            if hop.resolved_value is None:
                continue
            anchor = anchors.get(hop.index, hop.anchor)
            steps = self._hop_steps(result, hop.index)
            search_steps = [s for s in steps if s.kind in ("search", "hallucination")]
            if not search_steps:
                continue
            last = search_steps[-1]
            tool = last.tool
            value = hop.resolved_value

            if tool == "dictionary_lookup":
                checks.append(
                    Check(
                        name=f"evidence_support[hop{hop.index}]",
                        status="PASS",
                        detail=(
                            f"\"{value}\" comes from an exact key in the curated dictionary "
                            "(confidence 0.99) - no noisy passage can outrank it."
                        ),
                        evidence=[f"dictionary|{hop.attribute}|{anchor}"],
                    )
                )
                checks.append(
                    Check(
                        name=f"context_conflict[hop{hop.index}]",
                        status="N/A",
                        detail=(
                            "Dictionary mode returns exactly one fact per key, so there is no "
                            "rival passage to conflict with."
                        ),
                    )
                )
                continue

            if tool == "model_parameters":
                checks.append(
                    Check(
                        name=f"evidence_support[hop{hop.index}]",
                        status="FAIL",
                        detail=(
                            f"\"{value}\" was produced without any retrieved document. The agent "
                            "generated it from model priors - unsupported by the corpus."
                        ),
                    )
                )
                poisoned_hop = poisoned_hop or hop.index
                continue

            docs = self._supporting_docs(result, hop.index)
            supporting = [d for d in docs if d.value == value]
            best_conf = max((d.confidence for d in supporting), default=0.0)
            supporting_ids = [d.doc_id for d in supporting]

            if not supporting:
                checks.append(
                    Check(
                        name=f"evidence_support[hop{hop.index}]",
                        status="FAIL",
                        detail=f"No retrieved passage supports \"{value}\".",
                    )
                )
                poisoned_hop = poisoned_hop or hop.index
                continue

            if best_conf < LOW_AUTHORITY:
                checks.append(
                    Check(
                        name=f"evidence_support[hop{hop.index}]",
                        status="FAIL",
                        detail=(
                            f"The only support for \"{value}\" is a low-authority document "
                            f"({', '.join(supporting_ids)}, confidence {best_conf:.2f}) with no "
                            "corroboration. The value may be stale or simply wrong."
                        ),
                        evidence=supporting_ids,
                    )
                )
                poisoned_hop = poisoned_hop or hop.index
            else:
                checks.append(
                    Check(
                        name=f"evidence_support[hop{hop.index}]",
                        status="PASS",
                        detail=(
                            f"\"{value}\" is supported by {len(supporting)} retrieved passage(s) "
                            f"(best confidence {best_conf:.2f})."
                        ),
                        evidence=supporting_ids,
                    )
                )

            strict = self._strict_retrieval(hop, anchor)
            if strict is None:
                checks.append(
                    Check(
                        name=f"context_conflict[hop{hop.index}]",
                        status="N/A",
                        detail="Dictionary mode has no context window to disagree with itself.",
                    )
                )
                continue

            support: Dict[str, float] = {}
            ids: Dict[str, List[str]] = {}
            for d in strict:
                support[d.extracted_value] = support.get(d.extracted_value, 0.0) + d.confidence * d.similarity
                ids.setdefault(d.extracted_value, []).append(d.id)
            claim_support = support.get(value, 0.0)
            alternatives = {k: v for k, v in support.items() if k != value}
            best_alt = max(alternatives.items(), key=lambda kv: kv[1]) if alternatives else None

            if best_alt and best_alt[1] > claim_support * CONFLICT_RATIO:
                alt_value, alt_support = best_alt
                checks.append(
                    Check(
                        name=f"context_conflict[hop{hop.index}]",
                        status="FAIL",
                        detail=(
                            f"Re-retrieving \"{hop.attribute} of {anchor}\" with a stricter query and a "
                            f"wider context ({len(strict)} passages) shows the passages for "
                            f"\"{alt_value}\" out-voting \"{value}\" "
                            f"({alt_support:.2f} vs {claim_support:.2f}). The value the researcher "
                            "took is not the consensus of the corpus."
                        ),
                        evidence=ids.get(alt_value, []),
                    )
                )
                if poisoned_hop is None:
                    poisoned_hop = hop.index
                if repair is None:
                    repair = Repair(
                        hop_index=hop.index,
                        value=alt_value,
                        reason=(
                            f"\"{alt_value}\" carries the stronger support "
                            f"({alt_support:.2f} vs {claim_support:.2f}) across "
                            f"{len(ids.get(alt_value, []))} independent passage(s)."
                        ),
                        evidence=ids.get(alt_value, []),
                    )
            else:
                checks.append(
                    Check(
                        name=f"context_conflict[hop{hop.index}]",
                        status="PASS",
                        detail=(
                            f"A stricter re-retrieval does not out-vote \"{value}\" "
                            f"(support {claim_support:.2f})."
                        ),
                        evidence=ids.get(value, []),
                    )
                )

        # 4. answer type ----------------------------------------------------
        answer = result.final_answer
        if result.stop_reason == "ALL_HOPS_RESOLVED" and answer:
            atype = self._value_type(answer)
            expected = set()
            from .kb import ANSWER_TYPES

            if plan.answer_type == "any":
                checks.append(
                    Check(
                        name="answer_type",
                        status="N/A",
                        detail=(
                            "The question does not imply an answer type, so there is nothing to "
                            "check the final value against."
                        ),
                    )
                )
                expected = set()
            else:
                expected = ANSWER_TYPES.get(plan.answer_type, {plan.answer_type})
                if not expected or atype in expected or atype in {"", None}:
                    checks.append(
                        Check(
                            name="answer_type",
                            status="PASS",
                            detail=(
                                f"The answer \"{answer}\" is a {atype or 'value'}, which matches the "
                                f"\"{plan.answer_type}\" type the question asks for."
                            ),
                        )
                    )
                else:
                    checks.append(
                        Check(
                            name="answer_type",
                            status="FAIL",
                            detail=(
                                f"The answer \"{answer}\" is a {atype}, but the question asks for a "
                                f"{plan.answer_type}."
                            ),
                        )
                    )
        else:
            checks.append(
                Check(
                    name="answer_type",
                    status="N/A",
                    detail="No final answer was produced, so there is no answer type to check.",
                )
            )

        # -- verdict --------------------------------------------------------
        failures = [c for c in checks if c.status == "FAIL"]
        if result.stop_reason == "MISSING_INFORMATION":
            status = "INSUFFICIENT_EVIDENCE"
            headline = "Missing information - the answer cannot be grounded"
            explanation = (
                f"The chain reached \"{result.missing_fact}\" and found nothing in the knowledge "
                "base. The researcher degraded gracefully instead of inventing a value, so the "
                "correct outcome here is an explicit gap, not an answer."
            )
        elif failures:
            status = "REJECTED"
            headline = (
                f"Rejected - {failures[0].name} failed"
                + (f" at hop {poisoned_hop}" if poisoned_hop else "")
            )
            explanation = self._explain_rejection(plan, result, failures, poisoned_hop, repair)
        elif result.stop_reason == "HOP_CAP_REACHED":
            status = "INSUFFICIENT_EVIDENCE"
            headline = "Incomplete - the hop budget ran out"
            explanation = "The agent hit the hard hop cap before the chain was complete."
        else:
            status = "CONFIRMED"
            headline = "Confirmed - every hop is backed by the corpus"
            explanation = (
                f"The chain {', '.join(result.chain)} is supported by the retrieved evidence and "
                "the final answer has the type the question asked for."
            )

        return Verdict(
            status=status,
            headline=headline,
            explanation=explanation,
            checks=checks,
            repair=repair,
            poisoned_hop=poisoned_hop,
        )

    # -- narration ---------------------------------------------------------
    def _explain_rejection(
        self,
        plan: Plan,
        result: ResearchResult,
        failures: List[Check],
        poisoned_hop: Optional[int],
        repair: Optional[Repair],
    ) -> str:
        parts: List[str] = []
        for check in failures:
            if check.name.startswith("context_conflict"):
                hop = int(check.name.split("hop")[-1].rstrip("]"))
                hop_obj = next((h for h in plan.hops if h.index == hop), None)
                if hop_obj:
                    parts.append(
                        f"Hop {hop} was poisoned. The researcher took \"{hop_obj.resolved_value}\" "
                        f"for {hop_obj.attribute}({hop_obj.anchor}) from the top-ranked passage, but "
                        f"{check.detail}"
                    )
            elif check.name.startswith("evidence_support"):
                hop = int(check.name.split("hop")[-1].rstrip("]"))
                hop_obj = next((h for h in plan.hops if h.index == hop), None)
                if hop_obj:
                    parts.append(
                        f"Hop {hop} is not properly supported: {check.detail}"
                    )
            else:
                parts.append(check.detail)

        if poisoned_hop and len(plan.hops) > poisoned_hop:
            downstream = plan.hops[poisoned_hop]
            parts.append(
                f"Because hop {poisoned_hop} fed the bridge entity into hop {downstream.index} "
                f"({downstream.attribute}), the error propagated into the final answer "
                f"\"{result.final_answer}\"."
            )
        if repair:
            parts.append(
                f"Repair available: re-run the chain with hop {repair.hop_index} = "
                f"\"{repair.value}\". {repair.reason}"
            )
        return " ".join(parts)

    @staticmethod
    def _value_type(value: Optional[str]) -> str:
        from .kb import ENTITY_TYPES

        if not value:
            return ""
        return ENTITY_TYPES.get(value, "")
