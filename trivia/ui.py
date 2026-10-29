"""HTML renderers for the Streamlit app (everything is palette-coloured HTML)."""

from __future__ import annotations

import html
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .palette import PURPLE, SILVER
from .researcher import ResearchResult, Step
from .verifier import Check, Verdict


def esc(value: Any) -> str:
    return html.escape(str(value))


def html_block(*parts: Any) -> str:
    """Join HTML fragments without ever emitting a blank line.

    Streamlit renders markdown, and CommonMark ends a raw-HTML block at a
    blank line - so an empty conditional fragment would leak raw tags into
    the page. Dropping empty parts keeps every block parseable.
    """
    return "\n".join(p for p in parts if p)


_PILL_KINDS = {
    "ok": "mh-pill",
    "bad": "mh-pill mh-pill-bad",
    "grey": "mh-pill mh-pill-grey",
    "accent": "mh-pill mh-pill-accent",
}


def pill(text: str, kind: str = "grey") -> str:
    """A small rounded status badge."""
    cls = _PILL_KINDS.get(kind, "mh-pill")
    return f'<span class="{cls}">{esc(text)}</span>'


# --------------------------------------------------------------------------


def topbar(brand: str = "Multi-Hop Trivia", tag: str = "ReAct QA Workbench") -> str:
    """Compact product bar shown above the page header (the gear sits beside it)."""
    return f"""
    <div class="mh-navbar">
      <span class="mh-brand-mark">MH</span>
      <span class="mh-brand">
        <span class="mh-brand-name">{esc(brand)}</span>
        <span class="mh-brand-sub">{esc(tag)}</span>
      </span>
      <span class="mh-nav-badge"><span class="mh-nav-dot"></span>Local &middot; Offline</span>
    </div>
    """


def settings_section(index: str, title: str, caption: str = "") -> str:
    """Small numbered heading used inside the settings popover."""
    cap = f'<span class="mh-settings-caption">{esc(caption)}</span>' if caption else ""
    return (
        '<div class="mh-settings-head">'
        f'<span class="mh-settings-num">{esc(index)}</span>'
        f'<span class="mh-settings-title">{esc(title)}</span>'
        f"{cap}</div>"
    )


def hero(kicker: str, title: str, subtitle: str) -> str:
    return f"""
    <div class="mh-hero">
      <span class="mh-kicker"><span class="mh-dot"></span>{esc(kicker)}</span>
      <h1>{esc(title)}</h1>
      <p>{esc(subtitle)}</p>
    </div>
    """


def question_banner(label: str, question: str, teaching: str = "") -> str:
    teaching_html = f'<div class="mh-teach">{esc(teaching)}</div>' if teaching else ""
    return f"""
    <div class="mh-question">
      <div class="mh-label">{esc(label)}</div>
      <div class="mh-q">{esc(question)}</div>
      {teaching_html}
    </div>
    """


def agent_cards(planner_body: str, researcher_body: str, verifier_body: str,
                researcher_bad: bool = False, verifier_bad: bool = False,
                verifier_missing: bool = False) -> str:
    def card(title: str, role: str, body: str, bad: bool = False) -> str:
        cls = "mh-agent mh-agent-bad" if bad else "mh-agent mh-agent-ok"
        return f'<div class="{cls}"><h4>{esc(title)}</h4><div class="mh-role">{esc(role)}</div><div class="mh-body">{body}</div></div>'

    return f"""
    <div class="mh-agents">
      {card("Planner", "question decomposition", planner_body)}
      {card("Researcher", "ReAct loop", researcher_body, researcher_bad)}
      {card("Verifier", "evidence review", verifier_body, verifier_bad or verifier_missing)}
    </div>
    """


def idle_block(changed: str = "") -> str:
    """Placeholder shown before the pipeline has been run."""
    steps = (
        ("Planner", "splits the question into an ordered list of hops"),
        ("Researcher", "runs the Thought / Action / Observation loop"),
        ("Verifier", "re-reads the evidence and audits every hop"),
    )
    cards = "".join(
        f'<div class="mh-idle-step"><b>{esc(title)}</b><span>{esc(body)}</span></div>'
        for title, body in steps
    )
    if changed:
        label = "Settings changed"
        heading = "Ready to run again"
        body = (
            f"You changed the {changed}. The previous result has been cleared so that "
            "nothing on screen contradicts your settings. Open <b>&#9881; Settings</b> and "
            "press <b>Run pipeline</b> to run the agent on the current settings."
        )
    else:
        label = "Ready to run"
        heading = "The pipeline has not been run yet"
        body = (
            "Open <b>&#9881; Settings</b> to choose a scenario and the retrieval settings, "
            "then press <b>Run pipeline</b>. Nothing is executed until you do."
        )
    return f"""
    <div class="mh-idle">
      <div class="mh-label">{esc(label)}</div>
      <h4>{esc(heading)}</h4>
      <p>{body}</p>
      <div class="mh-idle-steps">{cards}</div>
    </div>
    """


def plan_block(plan, sub_questions: Sequence[str], notes: Sequence[str]) -> str:
    items = "".join(f"<li>{esc(q)}</li>" for q in sub_questions)
    note_html = "".join(f"<div>{esc(n)}</div>" for n in notes)
    return f"""
    <div class="mh-plan">
      <h4>Planner output &mdash; hop decomposition</h4>
      <ol>{items}</ol>
      <div class="mh-meta">
        <b>strategy:</b> {esc(plan.strategy)} &nbsp;&middot;&nbsp;
        <b>answer type:</b> {esc(plan.answer_type)} &nbsp;&middot;&nbsp;
        <b>hops:</b> {plan.n_hops}
      </div>
      <div class="mh-meta">{note_html}</div>
    </div>
    """


# --------------------------------------------------------------------------


_STATE_META = {
    "ok": ("RESOLVED", "mh-state-ok"),
    "bridge": ("BRIDGE", "mh-state-grey"),
    "not_found": ("NO EVIDENCE", "mh-state-bad"),
    "missing": ("MISSING INFORMATION", "mh-state-bad"),
    "unsupported": ("UNSUPPORTED", "mh-state-bad"),
    "memory": ("CACHE HIT", "mh-state-ok"),
}


def _evidence_rows(step: Step) -> str:
    if not step.evidence:
        if step.observation and step.kind == "search" and step.tool == "dictionary_lookup":
            return (
                '<div class="mh-evi"><div class="mh-evi-cite">'
                "Source document (curated): " + esc(step.observation.split("(")[0]) +
                "</div></div>"
            )
        return ""
    rows = []
    for ev in step.evidence:
        cls = "mh-evi-row"
        if ev.decoy:
            cls += " mh-evi-decoy"
        elif ev.role != "candidate":
            cls += " mh-evi-noise"
        tags = []
        if ev.decoy:
            tags.append('<span class="mh-pill mh-pill-bad">low authority</span>')
        if ev.role != "candidate":
            tags.append('<span class="mh-pill mh-pill-grey">irrelevant</span>')
        value = f" &rarr; <b>{esc(ev.value)}</b>" if ev.value else ""
        rows.append(
            f'<div class="{cls}">'
            f'<span class="mh-evi-id">{esc(ev.doc_id)}</span>'
            f'<span class="mh-evi-txt">{esc(ev.source)}{value} {" ".join(tags)}</span>'
            f'<span class="mh-evi-num">sim {ev.similarity:.3f} &middot; conf {ev.confidence:.2f}</span>'
            f"</div>"
        )
    return f'<div class="mh-evi">{"".join(rows)}</div>'


def step_html(step: Step, bad: bool = False) -> str:
    state, state_cls = _STATE_META.get(step.status, (step.status.upper(), "mh-state-grey"))
    kind_badge = {
        "search": "ACTION",
        "memory": "MEMORY",
        "accept": "REPAIR",
        "hallucination": "HALLUCINATION",
        "bridge": "BRIDGE",
    }.get(step.kind, step.kind.upper())

    action_html = ""
    if step.kind == "search" or step.kind == "memory":
        action_html = (
            '<div class="mh-block mh-action">'
            f'<span class="mh-tag">{esc(kind_badge)}</span><code>{esc(step.action)}</code>'
            "</div>"
        )
    elif step.kind == "accept":
        action_html = (
            '<div class="mh-block mh-action">'
            f'<span class="mh-tag">ACTION</span><code>{esc(step.action)}</code>'
            "</div>"
        )
    elif step.kind == "hallucination":
        action_html = (
            '<div class="mh-block mh-action">'
            f'<span class="mh-tag">ACTION</span><code>{esc(step.action)}</code>'
            "</div>"
        )

    obs_html = (
        '<div class="mh-block mh-observation">'
        f'<span class="mh-tag">OBSERVATION</span><span class="mh-obs-text">{esc(step.observation)}</span>'
        "</div>"
    )

    notes = "".join(f"<div>&bull; {esc(n)}</div>" for n in step.notes)
    notes_html = f'<div class="mh-note">{notes}</div>' if notes else ""

    rule_html = (
        f'<div class="mh-note"><b>selection rule:</b> {esc(step.rule)}</div>' if step.rule else ""
    )

    cls = "mh-step"
    if bad:
        cls += " mh-step-bad"
    elif step.kind in ("accept", "bridge"):
        cls += " mh-step-repair"

    return html_block(
        f'<div class="{cls}">',
        '<div class="mh-step-top">',
        f'<span class="mh-badge">HOP {step.hop}</span>',
        f'<span class="mh-tool">{esc(step.tool)}</span>',
        f'<span class="mh-state {state_cls}">{esc(state)}</span>',
        f'<span class="mh-evi-num">call #{step.action_no}</span>',
        "</div>",
        f'<div class="mh-block mh-thought"><span class="mh-tag">Thought</span>{esc(step.thought)}</div>',
        action_html,
        obs_html,
        rule_html,
        notes_html,
        _evidence_rows(step),
        "</div>",
    )


def trace_block(result: ResearchResult, bad_hop: Optional[int] = None,
                title: str = "ReAct trace", subtitle: str = "") -> str:
    steps = "".join(
        step_html(step, bad=step.hop == bad_hop) for step in result.steps
    )
    sub = f'<div class="mh-note">{esc(subtitle)}</div>' if subtitle else ""
    return f'<div class="mh-trace"><h3>{esc(title)}</h3>{sub}{steps}{terminal_html(result)}</div>'


def terminal_html(result: ResearchResult) -> str:
    """The strip that marks the exact moment the loop decided to stop."""
    bad = result.stop_reason != "ALL_HOPS_RESOLVED"
    cls = "mh-terminal mh-terminal-bad" if bad else "mh-terminal"
    label = "LOOP TERMINATED - NO ANSWER" if bad else "FINAL ANSWER - LOOP TERMINATED"
    return f"""
    <div class="{cls}">
      <div class="mh-terminal-label">{esc(label)}</div>
      <div class="mh-terminal-value">{esc(result.final_answer or "-")}</div>
      <div class="mh-terminal-note">{esc(result.stop_detail)}</div>
    </div>
    """


def final_block(result: ResearchResult, verdict_status: str = "CONFIRMED",
                headline: str = "", label: Optional[str] = None) -> str:
    bad = result.stop_reason != "ALL_HOPS_RESOLVED" or verdict_status == "REJECTED"
    cls = "mh-final mh-final-bad" if bad else "mh-final"
    note = result.stop_detail
    if result.chain:
        note = "chain: " + " -> ".join(result.chain) + " | " + note
    if label is None:
        label = "FINAL ANSWER (UNSUPPORTED)" if result.hallucinated else "FINAL ANSWER"
    return f"""
    <div class="{cls}">
      <div class="mh-final-label">{esc(label)}</div>
      <div class="mh-final-value">{esc(result.final_answer or "-")}</div>
      <div class="mh-final-note">{esc(note)}</div>
    </div>
    """


def fail_block(title: str, body: str) -> str:
    return f'<div class="mh-fail"><h4>{esc(title)}</h4><div>{body}</div></div>'


# --------------------------------------------------------------------------


def verifier_block(verdict: Verdict, title: str = "Verifier report") -> str:
    cls = "mh-verdict-bad" if verdict.status == "REJECTED" else "mh-verdict-ok"
    if verdict.status == "INSUFFICIENT_EVIDENCE":
        cls = "mh-verdict-bad"
    rows = []
    for check in verdict.checks:
        status_cls = {
            "PASS": "mh-status-pass",
            "FAIL": "mh-status-fail",
            "WARN": "mh-status-warn",
            "N/A": "mh-status-na",
        }.get(check.status, "mh-status-na")
        rows.append(
            '<div class="mh-check">'
            f'<span class="mh-status {status_cls}">{esc(check.status)}</span>'
            f'<span class="mh-check-name">{esc(check.name)}</span>'
            f"<span>{esc(check.detail)}</span>"
            "</div>"
        )
    repair_html = ""
    if verdict.repair:
        repair_html = (
            '<div class="mh-note"><b>Repair:</b> hop '
            f"{esc(verdict.repair.hop_index)} is re-run with <b>{esc(verdict.repair.value)}</b>. "
            f"{esc(verdict.repair.reason)}</div>"
        )
    return html_block(
        f'<div class="mh-verdict {cls}">',
        f"<h4>{esc(title)} &mdash; {esc(verdict.headline)}</h4>",
        f'<div class="mh-expl">{esc(verdict.explanation)}</div>',
        repair_html,
        f'<div style="margin-top:10px">{"".join(rows)}</div>',
        "</div>",
    )


def kv_block(items: Sequence[Sequence[str]]) -> str:
    cells = "".join(
        f'<div class="mh-kv-item"><span>{esc(k)}</span> <b>{esc(v)}</b></div>' for k, v in items
    )
    return f'<div class="mh-kv">{cells}</div>'


def memory_table(memory: Sequence[Dict[str, Any]]) -> str:
    if not memory:
        return '<div class="mh-note">Session memory is empty - no fact has been stored yet.</div>'
    rows = "".join(
        "<tr style='border-bottom:1px dotted rgba(197,193,193,0.45)'>"
        f"<td style='padding:6px 8px'>{esc(m.get('attribute'))}</td>"
        f"<td style='padding:6px 8px'>{esc(m.get('anchor'))}</td>"
        f"<td style='padding:6px 8px'><b style='color:{PURPLE}'>{esc(m.get('value'))}</b></td>"
        f"<td style='padding:6px 8px'>{esc(m.get('tool'))}</td>"
        f"<td style='padding:6px 8px'>hop {esc(m.get('hop'))}</td>"
        "</tr>"
        for m in memory
    )
    head = (
        '<thead><tr style="color:#5C5468; text-align:left; font-size:0.66rem; '
        f'letter-spacing:1.1px; text-transform:uppercase; border-bottom:1px solid {SILVER}">'
        '<th style="padding:6px 8px">attribute</th>'
        '<th style="padding:6px 8px">anchor</th>'
        '<th style="padding:6px 8px">value</th>'
        '<th style="padding:6px 8px">tool</th>'
        '<th style="padding:6px 8px">stored</th>'
        "</tr></thead>"
    )
    return (
        '<table style="width:100%; border-collapse:collapse; font-size:0.82rem; color:#2A2233">'
        f"{head}<tbody>{rows}</tbody></table>"
    )
