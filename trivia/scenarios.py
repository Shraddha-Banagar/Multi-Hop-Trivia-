"""Scenario catalogue for the demo.

Each scenario is a question plus the teaching point it is built to show.
The questions are ordinary multi-hop trivia questions; the differences in
behaviour come from the *state of the corpus*, not from hard-coded answers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Scenario:
    key: str
    title: str
    question: str
    tag: str
    teaching: str
    expectation: str
    outcome: str


SCENARIOS: List[Scenario] = [
    Scenario(
        key="s1",
        title="Scenario 1 - Mayor of a capital",
        question="Who is the mayor of the capital of France?",
        tag="standard",
        teaching="Canonical two-hop chain: capital(France) -> mayor(city).",
        expectation="Anne Hidalgo",
        outcome="Both hops resolve, the verifier confirms, the answer is Anne Hidalgo.",
    ),
    Scenario(
        key="s2",
        title="Scenario 2 - Reverse lookup chain",
        question="What is the capital of the country whose largest city is Sydney?",
        tag="standard",
        teaching="The first hop walks the fact graph backwards (city -> country).",
        expectation="Canberra",
        outcome="Sydney is the largest city of Australia; Australia -> Canberra.",
    ),
    Scenario(
        key="s3",
        title="Scenario 3 - Film -> person -> place",
        question="What is the birthplace of the director of the film 'Jurassic Park'?",
        tag="standard",
        teaching="Three entity types in a row: film -> person -> city.",
        expectation="Cincinnati",
        outcome="Jurassic Park -> Steven Spielberg -> Cincinnati.",
    ),
    Scenario(
        key="s4",
        title="Scenario 4 - Missing fact",
        question="Who is the mayor of the capital of Germany?",
        tag="failure",
        teaching="The corpus has no 'mayor of Berlin' fact. The agent must not invent one.",
        expectation="UNKNOWN (or the retired mayor, if the noisy web doc is retrieved)",
        outcome=(
            "Dictionary mode: NOT FOUND -> graceful degradation. Chroma mode: the noisy forum "
            "document supplies a stale name, which the verifier rejects as unsupported."
        ),
    ),
    Scenario(
        key="s5",
        title="Scenario 5 - Poisoned first hop",
        question="What is the capital of the country where the Eiffel Tower is located?",
        tag="poison",
        teaching="A keyword-stuffed forum page outranks the encyclopaedia entry and poisons hop 2.",
        expectation="Paris",
        outcome=(
            "Chroma mode with small k: hop 1 resolves to Japan, hop 2 returns Tokyo, and the "
            "verifier catches the poisoning and repairs the chain. Large k restores the truth "
            "through redundancy."
        ),
    ),
]

CUSTOM_SCENARIO = Scenario(
    key="custom",
    title="Custom question",
    question="",
    tag="custom",
    teaching="Any question the fact graph can ground - the graph planner handles it.",
    expectation="?",
    outcome="Planned by the graph planner, executed by the same ReAct loop.",
)


def by_key(key: str) -> Scenario:
    for scenario in SCENARIOS:
        if scenario.key == key:
            return scenario
    return CUSTOM_SCENARIO
