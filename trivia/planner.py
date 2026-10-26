"""The Planner agent.

The planner turns one multi-hop question into an ordered list of *hops*.
Each hop is a ``(attribute, anchor)`` pair; the anchor of a later hop is the
*bridge entity* produced by the previous hop (classic multi-hop chaining).

Two planners are implemented:

``PatternPlanner``  recognises the five canonical question shapes used by the
                    demo scenarios and produces a hand-shaped decomposition.
``GraphPlanner``    a generic fallback: it grounds every entity mentioned in
                    the question inside the fact graph and searches for the
                    two/three-hop path whose final attribute and answer type
                    best match the question. Used for custom questions.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .kb import (
    ALIASES,
    ATTRIBUTES,
    CURATED_FACTS,
    ENTITY_TYPES,
    canonical,
    normalize,
)


@dataclass
class Hop:
    index: int
    attribute: str
    anchor: str
    expect_type: List[str]
    question: str
    description: str
    anchor_is_bridge: bool = False
    bridge_label: str = ""
    resolved_value: Optional[str] = None
    status: str = "pending"

    def anchor_for(self, bridge: Optional[str]) -> str:
        return bridge if self.anchor_is_bridge and bridge else self.anchor

    def render(self, bridge: Optional[str]) -> str:
        subject = self.anchor_for(bridge)
        if self.anchor_is_bridge:
            subject = f"{self.bridge_label or 'the bridge entity'} found in hop {self.index - 1}"
        try:
            return self.question.format(subject=subject)
        except (KeyError, IndexError, ValueError):
            # A user-typed question may contain braces; never let that crash
            # the render - fall back to the raw question text.
            return self.question

    def describe(self) -> str:
        return f"{self.attribute}({self.anchor})"


@dataclass
class Plan:
    question: str
    hops: List[Hop]
    strategy: str
    answer_type: str
    notes: List[str] = field(default_factory=list)
    bridge_chain: List[str] = field(default_factory=list)

    @property
    def n_hops(self) -> int:
        return len(self.hops)

    def sub_questions(self) -> List[str]:
        out: List[str] = []
        bridge: Optional[str] = None
        for hop in self.hops:
            out.append(hop.render(bridge))
            if hop.resolved_value:
                bridge = hop.resolved_value
        return out


# --------------------------------------------------------------------------


def infer_answer_type(question: str) -> str:
    q = question.lower()
    if re.search(r"\bwho\b|\bwhom\b", q):
        return "person"
    if "capital" in q:
        return "city"
    if re.search(r"\bwhere\b|birthplace|born|hometown|\bcity\b|\bcountry\b", q):
        return "place"
    return "any"


def _entity_type(name: str) -> str:
    return ENTITY_TYPES.get(canonical(name), "entity")


# --------------------------------------------------------------------------


def _hop(
    index: int,
    attribute: str,
    anchor: str,
    expect_type: Sequence[str],
    question: str,
    description: str,
    anchor_is_bridge: bool = False,
    bridge_label: str = "",
) -> Hop:
    return Hop(
        index=index,
        attribute=attribute,
        anchor=anchor,
        expect_type=list(expect_type),
        question=question,
        description=description,
        anchor_is_bridge=anchor_is_bridge,
        bridge_label=bridge_label,
    )


# --------------------------------------------------------------------------
# Pattern planner
# --------------------------------------------------------------------------

PATTERNS: List[Tuple[str, Any]] = [
    (
        "mayor-of-capital",
        re.compile(
            r"\bwho\s+is\s+the\s+(?P<role>mayor|governor|mayoress)\s+of\s+the\s+capital\s+of\s+(?P<country>[^?,.]+)",
            re.I,
        ),
    ),
    (
        "capital-of-country-where",
        re.compile(
            r"\bwhat\s+is\s+the\s+capital\s+of\s+the\s+country\s+where\s+(?P<entity>.+?)\s+is\s+located",
            re.I,
        ),
    ),
    (
        "capital-of-country-largest-city",
        re.compile(
            r"\bwhat\s+is\s+the\s+capital\s+of\s+the\s+country\s+whose\s+largest\s+city\s+is\s+(?P<city>[^?,.]+)",
            re.I,
        ),
    ),
    (
        "birthplace-of-director",
        re.compile(
            r"\bwhat\s+is\s+the\s+(?P<attr>birthplace|hometown)\s+of\s+the\s+(?:film|movie)?\s*director\s+of\s+(?:the\s+)?(?:film\s+)?['\"]?(?P<work>[^'\"]+?)['\"]?\s*\??$",
            re.I,
        ),
    ),
    (
        "nationality-of-director",
        re.compile(
            r"\bwhat\s+is\s+the\s+nationality\s+of\s+the\s+(?:film|movie)?\s*director\s+of\s+(?:the\s+)?(?:film\s+)?['\"]?(?P<work>[^'\"]+?)['\"]?\s*\??$",
            re.I,
        ),
    ),
    (
        "director-of-film",
        re.compile(
            r"\bwho\s+directed\s+(?:the\s+)?(?:film\s+)?['\"]?(?P<work>[^'\"]+?)['\"]?\s*\??$",
            re.I,
        ),
    ),
]

ROLE_ATTRIBUTE = {"mayor": "mayor", "mayoress": "mayor", "governor": "mayor"}

# Question shapes that expose *which relation* is being asked about.  Used to
# tell "who is the mayor of X" (answerable) apart from "what is the population
# of X" (a relation the knowledge base does not model).
_RELATION_PATTERNS: List[re.Pattern] = [
    re.compile(r"^\s*what(?:'s|s| is| are)?\s+the\s+([a-z][a-z\s-]*?)\s+of\b", re.I),
    re.compile(r"^\s*who(?:'s|s| is| are)?\s+the\s+([a-z][a-z\s-]*?)\s+of\b", re.I),
    re.compile(r"^\s*how\s+(?:many|much)\s+(?:is|are)?\s*the\s+([a-z][a-z\s-]*?)\s+of\b", re.I),
    re.compile(r"^\s*how\s+(?:many|much)\s+([a-z][a-z\s-]*?)\b", re.I),
]

# "which <X> ..." names the answer *type*, not the relation - only useful when
# X is something the schema does not model ("which population ...").
_WHICH_PATTERN = re.compile(
    r"^\s*which\s+([a-z][a-z\s-]*?)\s+(?:is|are|has|have|was|were)\b", re.I
)

_ANSWER_TYPE_WORDS = {
    "city", "cities", "country", "countries", "nation", "nations",
    "place", "places", "person", "people",
}


def _pattern_plan(question: str, answer_type: str) -> Optional[Plan]:
    for name, regex in PATTERNS:
        m = regex.search(question)
        if not m:
            continue
        groups = {k: (v or "").strip() for k, v in m.groupdict().items()}
        groups = {k: re.sub(r"^(the|a|an)\s+", "", v, flags=re.I) for k, v in groups.items()}

        if name == "mayor-of-capital":
            role = ROLE_ATTRIBUTE.get(groups["role"].lower(), "mayor")
            country = canonical(groups["country"])
            hops = [
                _hop(1, "capital", country, ["city"], "What is the capital of {subject}?",
                     f"Resolve the bridge: the capital city of {country}."),
                _hop(2, role, "", ["person"], "Who is the {attribute} of {subject}?",
                     f"Resolve the answer: the {role} of that city.",
                     anchor_is_bridge=True, bridge_label="the city"),
            ]
            hops[1].question = f"Who is the {role} of {{subject}}?"
            return Plan(question=question, hops=hops, strategy=f"pattern:{name}",
                        answer_type=answer_type,
                        notes=["Pattern match on 'the <role> of the capital of <country>'."])

        if name == "capital-of-country-where":
            entity = canonical(groups["entity"])
            hops = [
                _hop(1, "location", entity, ["country"], "In which country is {subject} located?",
                     f"Resolve the bridge: the country where {entity} is located."),
                _hop(2, "capital", "", ["city"], "What is the capital of {subject}?",
                     "Resolve the answer: the capital of that country.",
                     anchor_is_bridge=True, bridge_label="the country"),
            ]
            return Plan(question=question, hops=hops, strategy=f"pattern:{name}",
                        answer_type=answer_type,
                        notes=["Pattern match on 'the capital of the country where <entity> is located'."])

        if name == "capital-of-country-largest-city":
            city = canonical(groups["city"])
            hops = [
                _hop(1, "largest_city", city, ["country"], "Which country has {subject} as its largest city?",
                     f"Resolve the bridge: the country whose largest city is {city}."),
                _hop(2, "capital", "", ["city"], "What is the capital of {subject}?",
                     "Resolve the answer: the capital of that country.",
                     anchor_is_bridge=True, bridge_label="the country"),
            ]
            return Plan(question=question, hops=hops, strategy=f"pattern:{name}",
                        answer_type=answer_type,
                        notes=["Pattern match on 'the capital of the country whose largest city is <city>'."])

        if name in ("birthplace-of-director", "nationality-of-director"):
            work = canonical(groups["work"])
            second_attr = "birthplace" if name == "birthplace-of-director" else "nationality"
            expect = ["place", "city"] if second_attr == "birthplace" else ["person"]
            hops = [
                _hop(1, "director", work, ["person"], "Who directed {subject}?",
                     f"Resolve the bridge: the director of {work}."),
                _hop(2, second_attr, "", expect, f"What is the {second_attr} of {{subject}}?",
                     f"Resolve the answer: the {second_attr} of that person.",
                     anchor_is_bridge=True, bridge_label="the person"),
            ]
            return Plan(question=question, hops=hops, strategy=f"pattern:{name}",
                        answer_type=answer_type,
                        notes=[f"Pattern match on 'the {second_attr} of the director of <work>'."])

        if name == "director-of-film":
            work = canonical(groups["work"])
            hops = [
                _hop(1, "director", work, ["person"], "Who directed {subject}?",
                     f"Resolve the answer: the director of {work}."),
            ]
            return Plan(question=question, hops=hops, strategy=f"pattern:{name}",
                        answer_type=answer_type,
                        notes=["Pattern match on 'who directed <work>' - single hop."])
    return None


# --------------------------------------------------------------------------
# Graph planner (generic fallback)
# --------------------------------------------------------------------------


_ANSWER_SET = {
    "person": {"person"},
    "city": {"city", "place"},
    "place": {"place", "city", "country"},
    "country": {"country"},
    "any": {"person", "city", "place", "country"},
}


def _build_graph() -> Dict[str, List[Dict[str, Any]]]:
    """Directed fact graph: ``subject --attribute--> value``.

    Only the *forward* direction of every curated fact is kept.  The reverse
    reading of a fact ("the capital of Berlin is Germany") is not a
    meaningful query, so keeping it would let the planner propose nonsense
    hops such as "the capital of Berlin".
    """
    graph: Dict[str, List[Dict[str, Any]]] = {}
    for fact in CURATED_FACTS:
        graph.setdefault(fact.subject, []).append(
            {
                "to": fact.value,
                "attribute": fact.attribute,
                "side": "value",
                "type": fact.value_type,
                "types": {fact.value_type},
                "text": fact.text,
                "grounded": True,
            }
        )
    return graph


GRAPH = _build_graph()


def _alias_key(alias: str) -> str:
    """Normalised text of an alias key (without resolving it)."""
    key = re.sub(r"[^\w\s.&-]", " ", alias.lower())
    return re.sub(r"\s+", " ", key).strip()


def _mentioned_entities(question: str) -> List[str]:
    """Entities named in the question, resolved through the alias table.

    Longest match first, so "Steven Spielberg" wins over the alias
    "Spielberg" and "United States" wins over "America".
    """
    q = " " + normalize(question) + " "
    hits: List[str] = []
    for name in sorted(ENTITY_TYPES, key=len, reverse=True):
        n = normalize(name)
        if n and f" {n} " in q and name not in hits:
            hits.append(name)
    # aliases let a partial name resolve ("Spielberg" -> "Steven Spielberg")
    for alias, target in sorted(ALIASES.items(), key=lambda kv: -len(kv[0])):
        key = _alias_key(alias)
        if len(key) < 3 or f" {key} " not in q:
            continue
        resolved = canonical(target)
        if resolved in ENTITY_TYPES and resolved not in hits:
            hits.append(resolved)
    return sorted(set(hits), key=lambda n: -len(n))


def _attr_triggered(spec: Dict[str, Any], qwords: set, qtext: str) -> bool:
    """Does the question signal this attribute?

    A trigger may be a single word ("mayor") or a phrase ("largest city"),
    so the normalised question text is matched as well as the word bag.
    """
    for w in spec.get("words", []):
        if " " in w:
            if f" {w} " in qtext:
                return True
        elif w in qwords:
            return True
    return False


def _path_valid(path: Sequence[Dict[str, Any]]) -> bool:
    """Every bridge entity must have the type the next hop needs."""
    for i in range(len(path) - 1):
        bridge_types = path[i].get("types") or set()
        domain = ATTRIBUTES.get(path[i + 1]["attribute"], {}).get("domain", set())
        if domain and not (bridge_types & domain):
            return False
    return True


def _score_path(
    path: Sequence[Dict[str, Any]],
    answer_type: str,
    qwords: set,
    qtext: str,
) -> float:
    """Score a candidate chain.  ``path`` must be non-empty."""
    final = path[-1]
    spec = ATTRIBUTES.get(final["attribute"], {})
    score = 0.0
    if _attr_triggered(spec, qwords, qtext):
        score += 3.0
    if answer_type != "any":
        wanted = _ANSWER_SET.get(answer_type, {answer_type})
        types = final.get("types") or set()
        score += 2.0 if types & wanted else -2.0
    score -= 0.6 * len(path)
    if final.get("grounded"):
        # a hop that is backed by a curated fact beats a pure schema guess
        score += 0.8
    return score


def _graph_plan(question: str, answer_type: str) -> Optional[Plan]:
    """Generic planner: ground the question in the fact graph and pick the
    chain that best matches the wording and the expected answer type."""
    graph = GRAPH
    starts = _mentioned_entities(question)
    if not starts:
        return None
    qwords = set(re.findall(r"[a-z]+", question.lower()))
    qtext = " " + normalize(question) + " "

    best: Optional[Tuple[float, List[Dict[str, Any]]]] = None

    def offer(score: float, path: List[Dict[str, Any]]) -> None:
        nonlocal best
        if score <= 0:
            return
        if best is None or score > best[0]:
            best = (score, path)

    # 1 - chains that are actually backed by curated facts
    for start in starts:
        queue: deque = deque([(start, [], {start})])
        while queue:
            node, path, seen = queue.popleft()
            if len(path) >= 3:
                continue
            for edge in graph.get(node, []):
                # the start node may be revisited once (a country -> capital
                # -> country chain) but cycles are otherwise forbidden
                if edge["to"] in seen and edge["to"] != start:
                    continue
                new_path = path + [dict(edge, **{"from": node})]
                if _path_valid(new_path):
                    offer(_score_path(new_path, answer_type, qwords, qtext), new_path)
                queue.append((edge["to"], new_path, seen | {edge["to"]}))

    # 2 - schema-driven hops: an attribute can legitimately be asked about an
    # entity even when the curated dictionary holds no fact for it.  The
    # retriever may still have a document for it - that is exactly the
    # "stale web page" case the verifier is there to catch.
    for start in starts:
        start_type = _entity_type(start)
        for attr, spec in ATTRIBUTES.items():
            if start_type not in spec.get("domain", set()):
                continue
            types = set(spec.get("range", set()))
            edge = {
                "to": "",
                "attribute": attr,
                "side": "value",
                "type": next(iter(sorted(types)), "entity"),
                "types": types,
                "text": "",
                "grounded": False,
                "from": start,
            }
            offer(_score_path([edge], answer_type, qwords, qtext), [edge])

    if best is None:
        return None

    score, path = best
    hops: List[Hop] = []
    for i, edge in enumerate(path):
        attr = edge["attribute"]
        expect = sorted(edge.get("types") or {edge.get("type", "")})
        if i == 0:
            anchor = edge["from"]
            bridge_label = ""
        else:
            anchor = ""
            bridge_label = f"the {path[i - 1]['attribute'].replace('_', ' ')}"
        hops.append(
            _hop(
                i + 1,
                attr,
                anchor,
                expect,
                f"What is the {attr.replace('_', ' ')} of {{subject}}?",
                f"Resolve the {attr.replace('_', ' ')} of {edge['from']}.",
                anchor_is_bridge=(i > 0),
                bridge_label=bridge_label,
            )
        )
    grounded = [e for e in path if e.get("grounded")]
    notes = [
        f"Grounded '{path[0]['from']}' in the fact graph and searched for the best matching "
        f"{len(hops)}-hop path (score {score:.1f})."
    ]
    if not grounded:
        notes.append(
            "No curated fact matches the question, so the hop is derived from the attribute "
            "schema and the retriever decides whether a document supports it."
        )
    return Plan(
        question=question,
        hops=hops,
        strategy="graph:bfs",
        answer_type=answer_type,
        notes=notes,
    )


# --------------------------------------------------------------------------


def _question_relation(question: str) -> Optional[str]:
    """The relation a question asks about.

    ``"who is the mayor of X"`` -> ``"mayor"``.  Used to detect a question
    that asks for something the attribute schema simply does not model
    ("what is the population of Paris").
    """
    for pattern in _RELATION_PATTERNS:
        m = pattern.search(question)
        if m:
            relation = re.sub(r"\s+", " ", m.group(1).strip().lower())
            if relation:
                return relation
    m = _WHICH_PATTERN.search(question)
    if m:
        relation = re.sub(r"\s+", " ", m.group(1).strip().lower())
        if relation and relation not in _ANSWER_TYPE_WORDS:
            return relation
    return None


def _relation_supported(relation: str) -> bool:
    """Is the asked-for relation part of the attribute schema?"""
    tokens = set(re.findall(r"[a-z]+", relation))
    if not tokens:
        return True
    for spec in ATTRIBUTES.values():
        for w in spec.get("words", []):
            w_tokens = set(re.findall(r"[a-z]+", w))
            if w_tokens and w_tokens <= tokens:
                return True
    return False


def _unsupported_relation(question: str) -> Optional[str]:
    """The relation the question asks about that the schema cannot answer."""
    relation = _question_relation(question)
    if relation and not _relation_supported(relation):
        return relation
    return None


def _fallback_plan(
    question: str,
    answer_type: str,
    unsupported: Optional[str] = None,
) -> Plan:
    """Last resort when neither a template nor a graph path matched.

    The hop is anchored on an entity that actually occurs in the question, so
    the lookup can still succeed instead of being sent off with an empty key.
    When *nothing* can be grounded the original question is kept as the hop
    text, so the agent reports a clean "not in the knowledge base" instead of
    querying the empty key "".
    """
    grounded = _mentioned_entities(question)
    anchor = grounded[0] if grounded else ""
    qwords = set(re.findall(r"[a-z]+", question.lower()))
    qtext = " " + normalize(question) + " "

    if unsupported:
        # The question asks for a relation the schema does not model.  Answer
        # with the relation itself so the lookup honestly comes back empty
        # instead of silently returning some *other* fact.
        return Plan(
            question=question,
            hops=[
                _hop(1, unsupported.replace(" ", "_"), anchor, [],
                     question, f"Lookup of the unsupported relation '{unsupported}'."),
            ],
            strategy="fallback:single",
            answer_type=answer_type,
            notes=[
                f"The question asks for \"{unsupported}\", which is not one of the modelled "
                "attributes - the knowledge base has no such relation to look up.",
            ],
        )

    # prefer the attribute the question actually asks for
    triggered = [a for a, s in ATTRIBUTES.items() if _attr_triggered(s, qwords, qtext)]
    wanted = _ANSWER_SET.get(answer_type, {answer_type})
    typed = [a for a in triggered if set(ATTRIBUTES[a].get("range", set())) & wanted]

    attr = ""
    expect: List[str] = []
    if typed:
        attr = typed[0]
        expect = sorted(ATTRIBUTES[attr].get("range", set()))
    elif triggered:
        attr = triggered[0]
        expect = sorted(ATTRIBUTES[attr].get("range", set()))
    elif anchor:
        edges = GRAPH.get(anchor, [])
        matching = [e for e in edges if set(e.get("types") or set()) & wanted]
        chosen = matching[0] if matching else (edges[0] if edges else None)
        if chosen is not None:
            attr = chosen["attribute"]
            expect = sorted(chosen.get("types") or {chosen.get("type", "")})
    if not attr:
        attr = "country"
        expect = ["country"]

    if anchor:
        question_text = f"What is the {attr.replace('_', ' ')} of {{subject}}?"
        note = (
            "No template or graph path matched - falling back to a single generic hop. "
            f"The hop is anchored on the grounded entity '{anchor}'."
        )
    else:
        # nothing in the question exists in the knowledge base
        question_text = question
        note = (
            "No entity in the question could be grounded in the fact graph, so the original "
            "question is sent to the retriever unchanged. If it returns nothing, the fact "
            "genuinely is not in this knowledge base."
        )

    return Plan(
        question=question,
        hops=[
            _hop(1, attr, anchor, expect, question_text,
                 "Fallback single-hop lookup."),
        ],
        strategy="fallback:single",
        answer_type=answer_type,
        notes=[note],
    )


def plan_question(question: str) -> Plan:
    """Produce the hop decomposition for ``question``."""
    answer_type = infer_answer_type(question)
    unsupported = _unsupported_relation(question)
    if unsupported:
        plan = _fallback_plan(question, answer_type, unsupported=unsupported)
    else:
        plan = _pattern_plan(question, answer_type)
        if plan is None:
            plan = _graph_plan(question, answer_type)
        if plan is None:
            plan = _fallback_plan(question, answer_type)
    plan.notes.insert(0, f"Answer type inferred from the question: {answer_type}.")
    return plan
