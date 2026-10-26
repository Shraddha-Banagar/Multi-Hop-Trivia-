"""End-to-end pipeline: Planner -> Researcher -> Verifier (-> repair).

Kept separate from the Streamlit layer so the whole demo can be exercised
head-less (see ``tests/smoke.py``).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .planner import Plan, plan_question
from .researcher import ResearchResult, Researcher
from .tools import ToolRouter
from .verifier import Verdict, Verifier


@dataclass
class RunReport:
    question: str
    mode: str
    k: int
    max_hops: int
    plan: Plan
    result: ResearchResult
    verdict: Verdict
    repair_result: Optional[ResearchResult] = None
    repair_verdict: Optional[Verdict] = None
    router: Optional[ToolRouter] = None
    memory: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def final_answer(self) -> str:
        if self.repair_result and self.repair_result.final_answer:
            return self.repair_result.final_answer
        return self.result.final_answer or "-"

    @property
    def final_verdict(self) -> Verdict:
        return self.repair_verdict or self.verdict

    @property
    def was_repaired(self) -> bool:
        return self.repair_result is not None

    @property
    def diagnostics(self) -> Dict[str, Any]:
        scanned = 0
        returned = 0
        noise = 0
        for call in (self.router.calls if self.router else []):
            scanned = max(scanned, call.get("scanned", 0))
            returned += call.get("returned", 0)
            noise += call.get("noise", 0)
        return {
            "mode": self.mode,
            "k": self.k,
            "tool_calls": len(self.router.calls) if self.router else 0,
            "docs_scanned": scanned,
            "context_passages": returned,
            "irrelevant_passages": noise,
            "memory_entries": len(self.memory),
        }


def run_pipeline(
    question: str,
    mode: str = "dictionary",
    k: int = 4,
    max_hops: int = 4,
    allow_hallucination: bool = False,
    auto_correct: bool = True,
    memory: Optional[Any] = None,
) -> RunReport:
    """Run the full multi-agent pipeline for one question."""
    router = ToolRouter(mode=mode, k=k)
    if memory is not None:
        router.memory = memory

    plan = plan_question(question)
    researcher = Researcher(
        router=router,
        max_hops=max_hops,
        allow_hallucination=allow_hallucination,
    )
    result = researcher.run(question, plan)

    verifier = Verifier(router=router)
    verdict = verifier.verify(question, plan, result)

    repair_result: Optional[ResearchResult] = None
    repair_verdict: Optional[Verdict] = None

    if (
        auto_correct
        and verdict.status == "REJECTED"
        and verdict.repair is not None
        and result.stop_reason == "ALL_HOPS_RESOLVED"
    ):
        repair_plan = copy.deepcopy(plan)
        for hop in repair_plan.hops:
            hop.resolved_value = None
        forced = {verdict.repair.hop_index: verdict.repair.value}
        repair_result = Researcher(
            router=router,
            max_hops=max_hops,
            allow_hallucination=allow_hallucination,
        ).run(question, repair_plan, forced_bridge=forced, repaired=True)
        repair_verdict = Verifier(router=router).verify(question, repair_plan, repair_result)

    return RunReport(
        question=question,
        mode=mode,
        k=k,
        max_hops=max_hops,
        plan=plan,
        result=result,
        verdict=verdict,
        repair_result=repair_result,
        repair_verdict=repair_verdict,
        router=router,
        memory=router.memory.as_list(),
    )
