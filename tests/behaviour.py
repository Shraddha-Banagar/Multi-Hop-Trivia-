"""Assert the demo behaviours documented in the README."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trivia.pipeline import run_pipeline
from trivia.scenarios import SCENARIOS

S = {s.key: s.question for s in SCENARIOS}
checks = []


def expect(label, condition, detail=""):
    checks.append((label, condition, detail))


def run(question, **kw):
    return run_pipeline(question, **kw)


# 1 - standard scenarios succeed in both modes
for key, answer in (("s1", "Anne Hidalgo"), ("s2", "Canberra"), ("s3", "Cincinnati")):
    for mode in ("dictionary", "chroma"):
        r = run(S[key], mode=mode, k=3)
        expect(
            f"{key}/{mode} -> {answer}",
            r.result.final_answer == answer and r.final_verdict.status == "CONFIRMED",
            f"got {r.result.final_answer} / {r.final_verdict.status}",
        )

# 2 - scenario 4, dictionary: missing information
r = run(S["s4"], mode="dictionary", k=3)
expect(
    "s4/dictionary -> MISSING_INFORMATION",
    r.result.stop_reason == "MISSING_INFORMATION"
    and r.final_verdict.status == "INSUFFICIENT_EVIDENCE",
    f"got {r.result.stop_reason} / {r.final_verdict.status}",
)

# 3 - scenario 4, dictionary, hallucination mode: fabricates, verifier rejects
r = run(S["s4"], mode="dictionary", k=3, allow_hallucination=True)
expect(
    "s4/dictionary+hallucination -> asserted then REJECTED",
    r.result.hallucinated and r.final_verdict.status == "REJECTED",
    f"got hallucinated={r.result.hallucinated} / {r.final_verdict.status}",
)

# 4 - scenario 4, chroma: the stale low-authority answer is rejected
r = run(S["s4"], mode="chroma", k=3)
expect(
    "s4/chroma -> stale name REJECTED",
    r.result.final_answer == "Willy Brandt" and r.final_verdict.status == "REJECTED",
    f"got {r.result.final_answer} / {r.final_verdict.status}",
)

# 5 - scenario 5, dictionary: the truth
r = run(S["s5"], mode="dictionary", k=3)
expect(
    "s5/dictionary -> Paris CONFIRMED",
    r.result.final_answer == "Paris" and r.final_verdict.status == "CONFIRMED",
    f"got {r.result.final_answer} / {r.final_verdict.status}",
)

# 6 - scenario 5, chroma k=1: poisoned hop, rejected, repaired
r = run(S["s5"], mode="chroma", k=1)
expect(
    "s5/chroma k=1 -> Tokyo REJECTED on the first pass",
    r.result.final_answer == "Tokyo" and r.verdict.status == "REJECTED",
    f"got {r.result.final_answer} / {r.verdict.status}",
)
expect(
    "s5/chroma k=1 -> verifier blames hop 1",
    r.verdict.poisoned_hop == 1,
    f"got poisoned_hop={r.verdict.poisoned_hop}",
)
expect(
    "s5/chroma k=1 -> repair returns Paris",
    r.was_repaired
    and r.repair_result.final_answer == "Paris"
    and r.final_verdict.status == "CONFIRMED",
    f"got repaired={r.was_repaired} / {r.repair_result.final_answer if r.repair_result else None}",
)

# 7 - scenario 5, chroma k=3: redundancy repairs the hop by itself
r = run(S["s5"], mode="chroma", k=3)
expect(
    "s5/chroma k=3 -> Paris CONFIRMED (majority vote)",
    r.result.final_answer == "Paris" and r.final_verdict.status == "CONFIRMED",
    f"got {r.result.final_answer} / {r.final_verdict.status}",
)

# 8 - the hard hop cap really stops the loop
r = run(S["s1"], mode="dictionary", k=3, max_hops=1)
expect(
    "s1 with hop cap 1 -> HOP_CAP_REACHED",
    r.result.stop_reason == "HOP_CAP_REACHED",
    f"got {r.result.stop_reason}",
)

# 9 - session memory is written and reused
from trivia.tools import SessionMemory

mem = SessionMemory()
run(S["s1"], mode="dictionary", k=3, memory=mem)
expect(
    "session memory stores the hops",
    len(mem) == 2,
    f"got {len(mem)} entries",
)

# 10 - a hand-typed custom question is planned and answered
CUSTOM_QUESTIONS = {
    "What is the capital of France?": "Paris",
    "Who is the mayor of Paris?": "Anne Hidalgo",
    "Which city is the capital of Australia?": "Canberra",
    "Who directed Jurassic Park?": "Steven Spielberg",
    "What is the country of the Alcatraz Island?": "United States",
    "What is the largest city of Australia?": "Sydney",
    "Where is the Eiffel Tower?": "France",
}
for question, expected in CUSTOM_QUESTIONS.items():
    for mode in ("dictionary", "chroma"):
        r = run(question, mode=mode, k=3)
        expect(
            f"custom {question!r} ({mode}) -> {expected}",
            r.result.final_answer == expected,
            f"got {r.result.final_answer}",
        )

# 11 - a multi-hop custom question still chains
r = run("Who is the mayor of the city where the Eiffel Tower is located?", mode="chroma", k=3)
expect(
    "custom 3-hop chain -> Anne Hidalgo",
    r.result.final_answer == "Anne Hidalgo" and len(r.plan.hops) == 3,
    f"got {r.result.final_answer} in {len(r.plan.hops)} hop(s)",
)

# 12 - a partial name resolves through the alias table
r = run("Who is Spielberg?", mode="dictionary", k=3)
expect(
    "alias 'Spielberg' resolves to 'Steven Spielberg'",
    r.result.final_answer == "American",
    f"got {r.result.final_answer}",
)

# 13 - a relation the knowledge base does not model is NOT answered with a
#      different fact
r = run("What is the population of Paris?", mode="chroma", k=3)
expect(
    "unsupported relation -> MISSING_INFORMATION",
    r.result.stop_reason == "MISSING_INFORMATION",
    f"got {r.result.stop_reason} / {r.result.final_answer}",
)

# 14 - an entity that is not in the corpus is reported as missing
r = run("What is the capital of Italy?", mode="chroma", k=3)
expect(
    "unknown entity -> MISSING_INFORMATION",
    r.result.stop_reason == "MISSING_INFORMATION",
    f"got {r.result.stop_reason} / {r.result.final_answer}",
)

# 15 - the mock ChromaDB is persisted on disk and reloaded from it
from trivia.kb import (
    CURATED_FACTS,
    NOISY_FACTS,
    chroma_store_path,
    get_chroma,
    reset_chroma_cache,
)

store = chroma_store_path()
reset_chroma_cache()
built = get_chroma(force_rebuild=True)
expect(
    "chroma db is written to disk",
    built.source == "built" and (store / "manifest.json").exists(),
    f"source={built.source}, store={store}",
)
reset_chroma_cache()
reloaded = get_chroma()
expect(
    "chroma db is reloaded from disk",
    reloaded.source == "disk",
    f"got source={reloaded.source}",
)
expect(
    "reloaded index keeps every document",
    reloaded.count() == len(CURATED_FACTS) + len(NOISY_FACTS),
    f"got {reloaded.count()}",
)
expect(
    "reloaded index returns the same ranking",
    reloaded.query(["Eiffel Tower location country"], n_results=3)["ids"]
    == built.query(["Eiffel Tower location country"], n_results=3)["ids"],
    "the disk round-trip changed the retrieval order",
)

if __name__ == "__main__":
    failed = 0
    for label, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"   [{detail}]" if not ok else ""))
        failed += 0 if ok else 1
    print()
    print(f"{len(checks) - failed}/{len(checks)} behaviour checks passed")
    raise SystemExit(1 if failed else 0)
