"""Head-less smoke test for the ReAct engine (no Streamlit involved)."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trivia.pipeline import run_pipeline
from trivia.scenarios import SCENARIOS


def show(label, report):
    print("=" * 78)
    print(f"{label}")
    print(f"  question   : {report.question}")
    print(f"  plan       : {[h.render(None) for h in report.plan.hops]}  ({report.plan.strategy})")
    for step in report.result.steps:
        print(f"    [hop {step.hop} | {step.action_no}] {step.kind:<13} {step.status:<10} {step.action}")
        print(f"        obs: {step.observation}")
    print(f"  stop       : {report.result.stop_reason} ({report.result.stop_detail})")
    print(f"  answer     : {report.result.final_answer}")
    print(f"  verdict    : {report.verdict.status} - {report.verdict.headline}")
    for check in report.verdict.checks:
        print(f"      {check.status:<6} {check.name:<28} {check.detail[:110]}")
    if report.repair_result:
        print(f"  REPAIR run : {report.repair_result.final_answer}  verdict={report.repair_verdict.status}")
    print()


if __name__ == "__main__":
    for scenario in SCENARIOS:
        for mode, k in (("dictionary", 4), ("chroma", 1), ("chroma", 2), ("chroma", 3), ("chroma", 5)):
            report = run_pipeline(scenario.question, mode=mode, k=k, max_hops=4)
            show(f"{scenario.key} | {mode} k={k}", report)
