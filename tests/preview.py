"""Render a static HTML snapshot of the demo so the layout can be eyeballed.

    python tests/preview.py            -> writes preview.html
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trivia import styles, ui
from trivia.pipeline import run_pipeline
from trivia.scenarios import SCENARIOS

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "preview.html")


def page(title, report):
    plan = report.plan
    result = report.result
    verdict = report.verdict
    parts = [
        styles.CSS,
        "<div style='max-width:1100px;margin:0 auto;padding:18px'>",
        ui.hero(
            "Planner &middot; ReAct Researcher &middot; Verifier",
            "Multi-Hop Trivia Question Answering with ReAct",
            "One question, several hops, one verifiable answer - every Thought, Action and "
            "Observation is shown, and the verifier audits the evidence behind the chain.",
        ),
        ui.question_banner(
            f"{title} &middot; expected: ?",
            report.question,
            "teaching point",
        ),
        ui.agent_cards(
            f"Split the question into <b>{plan.n_hops} hop(s)</b> "
            f"(strategy <code>{ui.esc(plan.strategy)}</code>).",
            f"<b>{result.actions}</b> tool call(s). Stop reason: <b>{ui.esc(result.stop_reason)}</b>.",
            f"<b>{ui.esc(report.final_verdict.status)}</b> - {ui.esc(report.final_verdict.headline)}",
            researcher_bad=verdict.status == "REJECTED",
        ),
        ui.plan_block(plan, plan.sub_questions(), plan.notes),
        ui.trace_block(result, bad_hop=verdict.poisoned_hop),
        ui.final_block(result, verdict.status),
        ui.verifier_block(verdict),
    ]
    if report.repair_result:
        parts.append(ui.trace_block(report.repair_result, title="Recovery trace"))
        parts.append(ui.final_block(report.repair_result, report.repair_verdict.status))
    parts.append("</div>")
    return "\n".join(parts)


if __name__ == "__main__":
    blocks = []
    for scenario in SCENARIOS:
        mode, k = ("chroma", 1) if scenario.key == "s5" else ("dictionary", 4)
        report = run_pipeline(scenario.question, mode=mode, k=k, max_hops=4)
        blocks.append(f"<h2 style='color:#722F99'>{scenario.title}</h2>")
        blocks.append(page(scenario.title, report))
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Multi-Hop Trivia - preview</title>"
        "<style>body{background:#FFFFFF;margin:0;padding:0}"
        "hr{border:none;border-top:2px solid #C5C1C1;margin:26px 0}</style>"
        + styles.CSS
        + "</head><body><div style='max-width:1100px;margin:0 auto;padding:18px'>"
        + "<h1 style='color:#722F99'>Static preview of the Streamlit demo</h1>"
        + "<h2 style='color:#722F99'>Before the run (the state the app starts in)</h2>"
        + ui.idle_block()
        + "<hr>"
        + "</div>"
        + ("<hr>".join(blocks))
        + "</body></html>"
    )
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("wrote", OUT)
