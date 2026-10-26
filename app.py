"""Multi-Hop Trivia Question Answering with ReAct - interactive demo.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from trivia import styles, ui
from trivia.kb import (
    CURATED_FACTS,
    NOISY_FACTS,
    chroma_store_path,
    get_chroma,
    reset_chroma_cache,
)
from trivia.pipeline import run_pipeline
from trivia.scenarios import CUSTOM_SCENARIO, SCENARIOS, by_key
from trivia.tools import SessionMemory


st.set_page_config(
    page_title="Multi-Hop Trivia QA with ReAct",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(styles.CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------


def scenario_label(key: str) -> str:
    return by_key(key).title


def current_question(scenario_key: str, custom_text: str) -> str:
    if scenario_key == "custom":
        return custom_text.strip()
    return by_key(scenario_key).question


_SIGNATURE_LABELS = (
    "scenario",
    "question",
    "retrieval mode",
    "top-k",
    "hop cap",
    "auto-correct",
    "hallucination",
)


def signature_diff(old: tuple, new: tuple) -> str:
    """Human-readable list of the settings that changed since the last run."""
    changed = []
    for label, before, after in zip(_SIGNATURE_LABELS, old, new):
        if before != after:
            changed.append(
                f"{label} <b>{ui.esc(before)}</b> &rarr; <b>{ui.esc(after)}</b>"
            )
    return "; ".join(changed)


def sidebar() -> dict:
    with st.sidebar:
        st.markdown("### Multi-Hop Trivia")
        st.caption("ReAct + Planner + Verifier over a dictionary and a mock Chroma index.")

        st.markdown("#### 1. Scenario")
        keys = [s.key for s in SCENARIOS] + [CUSTOM_SCENARIO.key]
        scenario_key = st.selectbox(
            "Scenario",
            options=keys,
            format_func=scenario_label,
            index=0,
            key="scenario_key",
        )
        custom_text = ""
        if scenario_key == "custom":
            custom_text = st.text_input(
                "Your question",
                value="What is the capital of the country where the Hollywood Sign is located?",
                key="custom_question",
            )

        st.markdown("#### 2. Retrieval")
        mode_label = st.radio(
            "Tool",
            options=["Dictionary Lookup", "Chroma RAG"],
            horizontal=True,
            key="mode_label",
        )
        mode = "dictionary" if mode_label == "Dictionary Lookup" else "chroma"
        k = st.slider(
            "Top-k documents (Chroma RAG)",
            min_value=1,
            max_value=8,
            value=3,
            disabled=(mode == "dictionary"),
            key="k",
            help=(
                "How many passages the retriever puts in the context window. "
                "The dictionary always returns exactly one fact, so k does not apply there."
            ),
        )
        if mode == "dictionary":
            st.caption("Dictionary mode: exact key lookup, k is not applicable.")

        st.markdown("#### 3. Agent controls")
        max_hops = st.number_input(
            "Hard hop cap (max tool calls)",
            min_value=1,
            max_value=10,
            value=4,
            step=1,
            key="max_hops",
        )
        autocorrect = st.toggle(
            "Verifier auto-correct",
            value=True,
            key="autocorrect",
            help="Re-run the chain with the value the verifier trusts when a hop is rejected.",
        )
        hallucinate = st.toggle(
            "Simulate hallucination (unsafe mode)",
            value=False,
            key="hallucinate",
            help="When a fact is missing, let the model assert a value instead of degrading.",
        )

        col1, col2 = st.columns(2)
        run_clicked = col1.button("Run pipeline", type="primary", width="stretch")
        reset_clicked = col2.button("Reset memory", width="stretch")

        if reset_clicked:
            st.session_state["memory"] = SessionMemory()
            st.session_state.pop("last_report", None)
            st.session_state["signature"] = None
            st.rerun()

        st.markdown("#### Session memory")
        memory = st.session_state.get("memory") or SessionMemory()
        st.session_state["memory"] = memory
        st.markdown(ui.memory_table(memory.as_list()), unsafe_allow_html=True)

        st.markdown("#### Index statistics")
        store = chroma_store_path()
        rebuild_clicked = st.button("Rebuild vector index", width="stretch")
        if rebuild_clicked:
            reset_chroma_cache()
            collection = get_chroma(force_rebuild=True)
            st.toast("Vector index rebuilt on disk.", icon="\u2713")
        else:
            collection = get_chroma()
        st.markdown(
            ui.kv_block(
                [
                    ("documents in index", str(collection.count())),
                    ("curated facts", str(len(CURATED_FACTS))),
                    ("noisy web docs", str(len(NOISY_FACTS))),
                    ("vocabulary", str(len(collection._embedder.idf))),
                    ("store", str(store)),
                    (
                        "state",
                        {
                            "disk": "loaded from disk",
                            "built": "rebuilt and written to disk",
                            "memory": "in memory only",
                        }.get(collection.source, collection.source),
                    ),
                ]
            ),
            unsafe_allow_html=True,
        )
        if collection.source != "disk":
            st.caption(
                f"The index is persisted at `{store}`. It was created on this run and will be "
                "reused from disk next time."
            )

    return {
        "scenario_key": scenario_key,
        "question": current_question(scenario_key, custom_text),
        "mode": mode,
        "k": k,
        "max_hops": int(max_hops),
        "autocorrect": autocorrect,
        "hallucinate": hallucinate,
        "run_clicked": run_clicked,
    }


# --------------------------------------------------------------------------


def main() -> None:
    cfg = sidebar()

    if not cfg["question"]:
        st.warning("Type a question to run the pipeline.")
        return

    signature = (
        cfg["scenario_key"],
        cfg["question"],
        cfg["mode"],
        cfg["k"],
        cfg["max_hops"],
        cfg["autocorrect"],
        cfg["hallucinate"],
    )

    report = st.session_state.get("last_report")
    run_signature = st.session_state.get("signature")

    # The pipeline runs only when the user presses "Run pipeline".
    if cfg["run_clicked"]:
        report = run_pipeline(
            question=cfg["question"],
            mode=cfg["mode"],
            k=cfg["k"],
            max_hops=cfg["max_hops"],
            allow_hallucination=cfg["hallucinate"],
            auto_correct=cfg["autocorrect"],
            memory=st.session_state.get("memory"),
        )
        st.session_state["last_report"] = report
        st.session_state["signature"] = signature
        run_signature = signature

    # Settings that differ from the last executed run invalidate its result.
    # The outdated report is hidden and the change is listed, but nothing is
    # re-run automatically - only the button does that.
    change_note = ""
    if report is not None and run_signature is not None and run_signature != signature:
        change_note = signature_diff(run_signature, signature)
        report = None

    scenario = by_key(cfg["scenario_key"])

    # -- header ----------------------------------------------------------
    st.markdown(
        ui.hero(
            "Planner · ReAct Researcher · Verifier",
            "Multi-Hop Trivia Question Answering with ReAct",
            "One question, several hops, one verifiable answer - every Thought, Action and "
            "Observation is shown, and the verifier audits the evidence behind the chain.",
        ),
        unsafe_allow_html=True,
    )

    st.markdown(
        ui.question_banner(
            f"{scenario.title} · expected: {scenario.expectation}",
            cfg["question"],
            scenario.teaching,
        ),
        unsafe_allow_html=True,
    )

    if report is None:
        st.markdown(ui.idle_block(change_note), unsafe_allow_html=True)
        return

    plan = report.plan
    result = report.result
    verdict = report.verdict
    final_verdict = report.final_verdict

    # -- agent strip ------------------------------------------------------
    planner_body = (
        f"Split the question into <b>{plan.n_hops} hop(s)</b> "
        f"(strategy <code>{ui.esc(plan.strategy)}</code>). Answer type inferred: "
        f"{ui.pill(plan.answer_type, 'accent')}."
    )
    researcher_body = (
        f"<b>{result.actions}</b> tool call(s) of a {report.max_hops}-hop budget. "
        f"Stop reason: {ui.pill(result.stop_reason, 'grey')}."
    )
    if verdict.status == "REJECTED":
        researcher_body += " " + ui.pill("rejected by verifier", "bad")
    if result.hallucinated:
        researcher_body += " " + ui.pill("hallucinated", "bad")
    if report.was_repaired:
        verifier_body = (
            f"{ui.pill(verdict.status, 'bad')} on the first pass &rarr; repaired &rarr; "
            f"{ui.pill(final_verdict.status, 'ok')}"
        )
    else:
        verdict_kind = "bad" if final_verdict.status != "CONFIRMED" else "ok"
        verifier_body = (
            f"{ui.pill(final_verdict.status, verdict_kind)} &mdash; "
            f"{ui.esc(final_verdict.headline)}"
        )

    st.markdown(
        ui.agent_cards(
            planner_body,
            researcher_body,
            verifier_body,
            researcher_bad=(result.hallucinated or verdict.status == "REJECTED"),
            verifier_bad=(final_verdict.status == "REJECTED"),
            verifier_missing=(final_verdict.status == "INSUFFICIENT_EVIDENCE"),
        ),
        unsafe_allow_html=True,
    )

    # -- tabs -------------------------------------------------------------
    tab_trace, tab_context, tab_verifier = st.tabs(
        ["ReAct trace", "Retrieval context", "Verifier"]
    )

    with tab_trace:
        st.markdown(
            ui.plan_block(plan, plan.sub_questions(), plan.notes),
            unsafe_allow_html=True,
        )
        bad_hop = verdict.poisoned_hop
        subtitle = ""
        if bad_hop:
            subtitle = (
                f"Hop {bad_hop} is highlighted in red: the verifier rejected the value it "
                "produced and the rest of the chain inherited the mistake."
            )
        st.markdown(
            ui.trace_block(result, bad_hop=bad_hop, subtitle=subtitle),
            unsafe_allow_html=True,
        )

        if report.repair_result:
            st.markdown(
                ui.fail_block(
                    "Poisoned hop detected - the chain was re-run with the verified bridge",
                    f"<div>The verifier rejected hop {verdict.repair.hop_index if verdict.repair else '?'} "
                    f"and supplied <b>{ui.esc(verdict.repair.value if verdict.repair else '')}</b> "
                    "as the supported alternative. The researcher re-ran the chain from that hop.</div>",
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                ui.trace_block(
                    report.repair_result,
                    bad_hop=None,
                    title="Recovery trace (verifier-driven re-run)",
                    subtitle="The same ReAct loop, restarted with the corrected bridge entity.",
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                ui.final_block(
                    report.repair_result,
                    report.repair_verdict.status,
                    label="FINAL ANSWER - AFTER THE VERIFIER REPAIR",
                ),
                unsafe_allow_html=True,
            )
        else:
            label = None
            if verdict.status == "REJECTED":
                label = "FINAL ANSWER - REJECTED BY THE VERIFIER"
            elif result.hallucinated:
                label = "FINAL ANSWER - UNSUPPORTED"
            st.markdown(
                ui.final_block(result, verdict.status, label=label),
                unsafe_allow_html=True,
            )

    with tab_context:
        st.markdown("#### Retrieved passages across the whole run")
        rows = []
        for step in result.steps:
            for ev in step.evidence:
                rows.append(
                    {
                        "hop": step.hop,
                        "doc": ev.doc_id,
                        "source": ev.source,
                        "value": ev.value or "-",
                        "similarity": ev.similarity,
                        "confidence": ev.confidence,
                        "role": ev.role,
                        "decoy": ev.decoy,
                    }
                )
        if rows:
            st.dataframe(
                rows,
                column_config={
                    "hop": st.column_config.NumberColumn("hop", width="small"),
                    "doc": st.column_config.TextColumn("document id", width="medium"),
                    "source": st.column_config.TextColumn("source", width="medium"),
                    "value": st.column_config.TextColumn("extracted value", width="small"),
                    "similarity": st.column_config.NumberColumn("similarity", format="%.3f"),
                    "confidence": st.column_config.NumberColumn("confidence", format="%.2f"),
                    "role": st.column_config.TextColumn("role in context"),
                    "decoy": st.column_config.CheckboxColumn("low authority"),
                },
                hide_index=True,
                width="stretch",
            )
        else:
            st.info(
                "Dictionary mode returns exact facts, so there is no passage list - the "
                "context window is one curated fact wide."
            )

        diag = report.diagnostics
        st.markdown("#### Retrieval diagnostics")
        st.markdown(
            ui.kv_block(
                [
                    ("mode", report.mode),
                    ("k", str(report.k)),
                    ("tool calls", str(diag["tool_calls"])),
                    ("docs scanned", str(diag["docs_scanned"])),
                    ("passages in context", str(diag["context_passages"])),
                    ("irrelevant passages", str(diag["irrelevant_passages"])),
                    ("memory entries", str(diag["memory_entries"])),
                ]
            ),
            unsafe_allow_html=True,
        )
        st.markdown("#### Session memory")
        st.markdown(
            ui.memory_table(st.session_state.get("memory").as_list()),
            unsafe_allow_html=True,
        )

    with tab_verifier:
        st.markdown(
            ui.verifier_block(verdict, "Verifier report (first pass)"),
            unsafe_allow_html=True,
        )
        if report.repair_verdict:
            st.markdown(
                ui.verifier_block(
                    report.repair_verdict, "Verifier report (after the repair)"
                ),
                unsafe_allow_html=True,
            )
        st.markdown("#### Verifier checks, step by step")
        for check in verdict.checks:
            status_cls = {
                "PASS": "mh-status-pass",
                "FAIL": "mh-status-fail",
                "WARN": "mh-status-warn",
                "N/A": "mh-status-na",
            }.get(check.status, "mh-status-na")
            st.markdown(
                f'<div class="mh-check"><span class="mh-status {status_cls}">'
                f"{ui.esc(check.status)}</span>"
                f'<span class="mh-check-name">{ui.esc(check.name)}</span>'
                f"<span>{ui.esc(check.detail)}</span></div>",
                unsafe_allow_html=True,
            )



if __name__ == "__main__":
    main()
