"""Unit 4 - the Researcher agent (the ReAct loop).

    Thought  ->  Action  ->  Observation  ->  Thought  ->  ...

The loop is deliberately *not* a canned trace: it is executed for real
against the selected retrieval tool, and it terminates only when
:func:`finish_condition` says so (missing fact / hard hop cap / all hops
resolved).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .llm import MockLLM
from .planner import Hop, Plan
from .tools import Observation, ToolRouter


# --------------------------------------------------------------------------


def finish_condition(
    resolved_hops: int,
    total_hops: int,
    actions_taken: int,
    max_hops: int,
    hop_failed: bool,
) -> Tuple[bool, str]:
    """The single place where the ReAct loop is allowed to stop.

    Returns ``(should_stop, reason)``.
    """
    if hop_failed:
        return True, "MISSING_INFORMATION"
    if resolved_hops >= total_hops:
        return True, "ALL_HOPS_RESOLVED"
    if actions_taken >= max_hops:
        return True, "HOP_CAP_REACHED"
    return False, "CONTINUE"


# --------------------------------------------------------------------------


@dataclass
class Evidence:
    doc_id: str
    text: str
    similarity: float
    confidence: float
    value: Optional[str]
    role: str
    source: str
    decoy: bool


@dataclass
class Step:
    hop: int
    action_no: int
    kind: str  # "search" | "memory" | "accept" | "hallucination"
    thought: str
    action: str
    tool: str
    argument: str
    observation: str
    status: str
    value: Optional[str] = None
    value_type: Optional[str] = None
    rule: str = ""
    evidence: List[Evidence] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class ResearchResult:
    question: str
    steps: List[Step] = field(default_factory=list)
    hops: List[Hop] = field(default_factory=list)
    final_answer: Optional[str] = None
    stop_reason: str = "CONTINUE"
    stop_detail: str = ""
    actions: int = 0
    chain: List[str] = field(default_factory=list)
    hallucinated: bool = False
    missing_fact: Optional[str] = None
    repaired: bool = False

    @property
    def ok(self) -> bool:
        return self.stop_reason == "ALL_HOPS_RESOLVED"

    def steps_for_hop(self, hop_index: int) -> List[Step]:
        return [s for s in self.steps if s.hop == hop_index]


# --------------------------------------------------------------------------


class Researcher:
    """Executes the Thought -> Action -> Observation loop."""

    def __init__(
        self,
        router: ToolRouter,
        max_hops: int = 4,
        max_attempts_per_hop: int = 2,
        allow_hallucination: bool = False,
    ) -> None:
        self.router = router
        self.max_hops = max_hops
        self.max_attempts_per_hop = max_attempts_per_hop
        self.llm = MockLLM(
            allow_hallucination=allow_hallucination, mode=router.mode
        )
        self.actions = 0

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _evidence(obs: Observation) -> List[Evidence]:
        out: List[Evidence] = []
        for doc in obs.docs:
            out.append(
                Evidence(
                    doc_id=doc.id,
                    text=doc.text,
                    similarity=doc.similarity,
                    confidence=doc.confidence,
                    value=doc.extracted_value,
                    role=doc.role,
                    source=str(doc.metadata.get("source", "")),
                    decoy=doc.is_decoy,
                )
            )
        return out

    def _record_search(
        self,
        hop: Hop,
        anchor: str,
        obs: Observation,
        thought: str,
        selection_rule: str,
        value: Optional[str],
    ) -> Step:
        if obs.tool == "dictionary_lookup":
            action = f"dictionary_lookup({obs.query})"
        else:
            action = f'chroma_search("{obs.query}")'
        status = "ok" if value else "not_found"
        if value:
            observation = f"{hop.attribute}({anchor}) = {value}"
            if obs.tool == "chroma_search" and obs.value and obs.value != value:
                observation += (
                    f"  (the top-ranked passage said '{obs.value}', but "
                    f"{selection_rule})"
                )
            else:
                observation += f"  ({selection_rule})"
        else:
            observation = obs.message
        notes: List[str] = []
        if obs.tool == "chroma_search":
            notes.append(
                f"scanned {obs.scanned} documents, kept {obs.returned} in context, "
                f"{obs.noise} irrelevant to this hop."
            )
            decoys = [e for e in self._evidence(obs) if e.decoy]
            if decoys:
                notes.append(
                    "low-authority documents in context: " + ", ".join(e.doc_id for e in decoys)
                )
        else:
            notes.append(f"exact key lookup over {obs.scanned} curated facts.")
        return Step(
            hop=hop.index,
            action_no=self.actions,
            kind="search",
            thought=thought,
            action=action,
            tool=obs.tool,
            argument=obs.query,
            observation=observation,
            status=status,
            value=value,
            value_type=obs.value_type,
            rule=selection_rule,
            evidence=self._evidence(obs),
            notes=notes,
        )

    # -- main loop ---------------------------------------------------------
    def run(
        self,
        question: str,
        plan: Plan,
        forced_bridge: Optional[Dict[int, str]] = None,
        repaired: bool = False,
    ) -> ResearchResult:
        forced_bridge = forced_bridge or {}
        self.actions = 0
        result = ResearchResult(question=question, hops=plan.hops, repaired=repaired)
        bridge: Optional[str] = None
        resolved = 0
        hop_failed = False
        cap_hit = False

        for hop in plan.hops:
            anchor = hop.anchor_for(bridge)
            hop_value: Optional[str] = None
            attempt = 0

            while True:
                if self.actions >= self.max_hops:
                    cap_hit = True
                    break

                if hop.index in forced_bridge and attempt == 0:
                    forced_value = forced_bridge[hop.index]
                    hop_value = forced_value
                    hop.resolved_value = forced_value
                    self.actions += 1
                    result.steps.append(
                        Step(
                            hop=hop.index,
                            action_no=self.actions,
                            kind="accept",
                            thought=(
                                f"Hop {hop.index}: the Verifier rejected the retrieved value and "
                                f"re-ran the lookup. I am accepting the corrected bridge "
                                f"{forced_value} and continuing the chain from there."
                            ),
                            action=f"accept_verified_fact({hop.attribute}={forced_value})",
                            tool="verifier_repair",
                            argument=f"{hop.attribute}={forced_value}",
                            observation=f"bridge replaced with {forced_value} (verified support).",
                            status="ok",
                            value=forced_value,
                            rule="verifier-approved correction",
                            notes=["Error propagation broken: the second hop now uses the verified bridge."],
                        )
                    )
                    break

                if attempt == 0:
                    cached = self.router.memory.get(hop.attribute, anchor)
                    if cached and hop.anchor_is_bridge:
                        hop_value = cached["value"]
                        hop.resolved_value = hop_value
                        self.actions += 1
                        result.steps.append(
                            Step(
                                hop=hop.index,
                                action_no=self.actions,
                                kind="memory",
                                thought=(
                                    f"Hop {hop.index}: I already established \"{hop.attribute}\" of "
                                    f"{anchor} earlier in this session, so I read it from session "
                                    "memory instead of re-querying the index."
                                ),
                                action=f"memory_lookup({hop.attribute} | {anchor})",
                                tool="memory_lookup",
                                argument=f"{hop.attribute} | {anchor}",
                                observation=cached["value"],
                                status="ok",
                                value=hop_value,
                                value_type=cached.get("value_type", ""),
                                rule="session memory hit",
                                notes=[f"stored during hop {cached.get('hop')} via {cached.get('tool')}"],
                            )
                        )
                        break

                thought = self.llm.thought_for(hop, attempt, anchor)
                obs = self.router.search(
                    attribute=hop.attribute,
                    anchor=anchor,
                    expect_type=hop.expect_type,
                    attempt=attempt,
                )
                selection = self.llm.select(obs)
                self.actions += 1
                step = self._record_search(
                    hop, anchor, obs, thought, selection.rule, selection.value
                )
                if selection.runner_up:
                    step.notes.append(
                        f"competing value in context: {selection.runner_up} "
                        f"(votes {selection.votes})."
                    )
                result.steps.append(step)

                if selection.value:
                    hop_value = selection.value
                    hop.resolved_value = hop_value
                    self.router.remember(hop.attribute, anchor, obs, hop.index)
                    break

                attempt += 1
                if attempt >= self.max_attempts_per_hop:
                    break

            if cap_hit:
                result.steps.append(
                    Step(
                        hop=hop.index,
                        action_no=self.actions,
                        kind="search",
                        thought=(
                            f"Hop {hop.index} cannot start: the hard hop cap of {self.max_hops} "
                            "tool call(s) is already spent. I stop before guessing."
                        ),
                        action=f"stop(hop_cap={self.max_hops})",
                        tool="none",
                        argument=f"{hop.attribute} | {anchor}",
                        observation=(
                            f"HOP CAP REACHED after {self.actions} tool call(s) - the chain "
                            f"stopped before hop {hop.index} could be answered."
                        ),
                        status="not_found",
                        value=None,
                        rule="hard hop cap - the loop is not allowed to continue",
                        notes=["Lower the hop cap in the sidebar to see this, raise it to allow more hops."],
                    )
                )
                break

            if hop_value is None:
                hop.status = "failed"
                if anchor:
                    result.missing_fact = f"{hop.attribute} of {anchor}"
                    missing_text = (
                        f"no fact \"{hop.attribute}\" of {anchor} is present in the knowledge base"
                    )
                else:
                    result.missing_fact = (
                        f"{hop.attribute} of an entity the question does not name"
                    )
                    missing_text = (
                        f"no entity in the question has a \"{hop.attribute}\" in the knowledge base"
                    )
                if self.llm.allow_hallucination:
                    fake, snippet = self.llm.hallucinate(hop, anchor)
                    hop_value = fake
                    hop.resolved_value = fake
                    result.hallucinated = True
                    self.actions += 1
                    result.steps.append(
                        Step(
                            hop=hop.index,
                            action_no=self.actions,
                            kind="hallucination",
                            thought=self.llm.thought_hallucinate(hop, anchor, fake, snippet),
                            action=f"answer_from_parameters({hop.attribute}={fake})",
                            tool="model_parameters",
                            argument=f"{hop.attribute}={fake}",
                            observation=f"asserted without retrieved support: {fake}",
                            status="unsupported",
                            value=fake,
                            rule="no retrieved evidence - generated from model priors",
                            notes=["NO document in the corpus supports this value."],
                        )
                    )
                else:
                    hop_failed = True
                    result.steps.append(
                        Step(
                            hop=hop.index,
                            action_no=self.actions,
                            kind="search",
                            thought=self.llm.thought_missing(hop, anchor),
                            action="stop(missing_information)",
                            tool="none",
                            argument=f"{hop.attribute} | {anchor}",
                            observation=(
                                f"MISSING INFORMATION: {missing_text}."
                            ),
                            status="missing",
                            value=None,
                            rule="degrade gracefully instead of inventing a value",
                            notes=["The agent refuses to guess; the run ends with an explicit gap."],
                        )
                    )
                    break

            bridge = hop_value
            resolved += 1
            if hop.index < len(plan.hops):
                result.steps.append(
                    Step(
                        hop=hop.index,
                        action_no=self.actions,
                        kind="bridge",
                        thought=self.llm.thought_bridge(hop, hop_value, plan.hops[hop.index]),
                        action=f"chain_bridge(hop{hop.index} -> hop{hop.index + 1})",
                        tool="internal",
                        argument=f"{hop_value}",
                        observation=f"bridge entity: {hop_value}",
                        status="bridge",
                        value=hop_value,
                        rule="bridge handed to the next hop",
                    )
                )

        should_stop, reason = finish_condition(
            resolved_hops=resolved,
            total_hops=len(plan.hops),
            actions_taken=self.actions,
            max_hops=self.max_hops,
            hop_failed=hop_failed,
        )

        if reason == "MISSING_INFORMATION":
            result.stop_reason = "MISSING_INFORMATION"
            result.stop_detail = (
                f"the hop cap was never reached; the run stopped because the fact "
                f"\"{result.missing_fact}\" is absent from the knowledge base."
            )
            result.final_answer = "UNKNOWN - fact not in the knowledge base"
        elif reason == "HOP_CAP_REACHED":
            result.stop_reason = "HOP_CAP_REACHED"
            result.stop_detail = (
                f"the agent used its whole budget of {self.max_hops} tool calls without "
                "resolving every hop."
            )
            result.final_answer = "INCOMPLETE - hop budget exhausted"
        else:
            result.stop_reason = "ALL_HOPS_RESOLVED"
            result.stop_detail = (
                f"every hop in the plan resolved after {self.actions} tool call(s); "
                f"the hop cap was {self.max_hops}."
            )
            last = plan.hops[-1]
            result.final_answer = last.resolved_value
            chain = [plan.hops[0].anchor]
            for hop in plan.hops:
                if hop.resolved_value:
                    chain.append(hop.resolved_value)
            result.chain = chain

        result.actions = self.actions
        return result
