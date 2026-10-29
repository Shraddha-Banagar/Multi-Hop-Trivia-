# Multi-Hop Trivia Question Answering with ReAct

An interactive demo of a **multi-agent RAG system**: a *Planner* splits a multi-hop trivia
question into hops, a *Researcher* executes a real **ReAct** loop
(`Thought → Action → Observation`) over two interchangeable retrieval back-ends, and a
*Verifier* audits the evidence and catches a poisoned hop before it reaches the answer.

Everything runs locally and offline. The LLM is mocked, but the **control flow is real**:
the trace you see is produced by executing the loop, not by replaying a canned script.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open <http://localhost:8501>.

The app starts **idle**: open the **&#9881; settings menu** in the top-right header, pick a
scenario and the retrieval settings, then press **Run pipeline**. Nothing is executed until
you press it. If you change a setting after a run, the old result is cleared and the app
tells you what changed, so nothing on screen ever contradicts your settings - but it still
does not re-run on its own.

---

## 1. What the demo shows

| Scenario | Question | What it demonstrates |
|---|---|---|
| 1 | *Who is the mayor of the capital of France?* | Canonical two-hop chain `capital → mayor` |
| 2 | *What is the capital of the country whose largest city is Sydney?* | A hop that walks the fact graph **backwards** (city → country) |
| 3 | *What is the birthplace of the director of the film 'Jurassic Park'?* | Three entity types in a row: `film → person → city` |
| 4 | *Who is the mayor of the capital of Germany?* | **Missing information** – the corpus has no `mayor of Berlin` fact |
| 5 | *What is the capital of the country where the Eiffel Tower is located?* | **Poisoned first hop** – a keyword-stuffed forum page outranks the encyclopaedia entry and poisons hop 2 |
| custom | any question | The generic **graph planner** grounds the entities and searches for a path |

### Writing your own question

Pick **custom** in the settings menu and type anything. The planner grounds the entities of your
question in the fact graph (including through the alias table, so `Spielberg` resolves to
`Steven Spielberg` and `America` to `United States`), scores every candidate chain against
the wording and the expected answer type, and picks the best one:

| Your question | What happens |
|---|---|
| *What is the capital of France?* | one hop, answered `Paris` |
| *Who is the mayor of the city where the Eiffel Tower is located?* | three hops: `location → capital → mayor` |
| *Who is the mayor of Berlin?* | the curated dictionary has no Berlin mayor → `MISSING_INFORMATION`; in Chroma RAG the stale web document is found and **rejected** by the verifier |
| *What is the capital of Italy?* | Italy is not in the corpus → `MISSING_INFORMATION`, never a guess |
| *What is the population of Paris?* | `population` is not a modelled relation → the agent reports the gap instead of answering some *other* fact about Paris |

The last two rows matter: an unanswerable question must produce an **explicit gap**, never a
plausible-looking answer to a different question.

### The three failure/success paths worth clicking

1. **Scenario 4 + Dictionary Lookup** → the lookup returns `NOT FOUND`, the agent stops with
   `MISSING_INFORMATION` and answers with an explicit gap instead of a guess.
   Turn on *Simulate hallucination* to see the unsafe variant: the model asserts a plausible
   name and the verifier rejects it for lack of evidence.
2. **Scenario 4 + Chroma RAG** → the noisy web document supplies a *stale* name
   (a former mayor). The answer looks fine, but `evidence_support` fails because the only
   document backing it has confidence `0.34`.
3. **Scenario 5 + Chroma RAG + k = 1 or 2** → hop 1 resolves to *Japan*, hop 2 therefore
   returns *Tokyo*, and the poisoned hop is highlighted in red. The verifier re-retrieves
   with a stricter query, sees that *France* out-votes *Japan* (`1.12` vs `0.22`), rejects
   the chain and **repairs** it – the answer becomes *Paris*.
   Raise **k to 3** and the redundancy in the index repairs the hop on its own: the agent
   only trusts a value when a majority of the retrieved passages agree.

---

## 2. Architecture

```
app.py                  Streamlit UI (header settings menu + trace explorer + verifier report)
trivia/
  kb.py                 the corpus: 20 curated facts + 5 noisy web documents,
                        the mock TF-IDF embedder and the MockChromaCollection
  tools.py              the action space: dictionary_lookup, chroma_search, memory_lookup
  llm.py                the mocked LLM: thought templates + the context-reading policy
  planner.py            Unit 4 - question → ordered list of hops (pattern + graph planner)
  researcher.py         Unit 4 - the ReAct loop and the hard hop cap
  verifier.py           Unit 4 - the four evidence checks and the repair
  pipeline.py           Planner → Researcher → Verifier → (repair) → Verifier
  ui.py / styles.py     HTML renderers and the palette CSS
tests/
  behaviour.py          asserts every demo behaviour listed in this README
  smoke.py              head-less engine run over every scenario × mode × k
  app_test.py           head-less Streamlit render: asserts the app stays idle until
                        "Run pipeline" is pressed, and that a settings change clears the
                        result without re-running
  preview.py            writes a static preview.html of the whole UI
```

### The two retrieval back-ends (Unit 3)

| | Dictionary Lookup | Chroma RAG |
|---|---|---|
| Mechanism | exact `(attribute, anchor)` key | cosine similarity over an embedded document index |
| Result per call | exactly one curated fact | the *top-k* passages, ranked |
| Noise | impossible | the corpus contains 5 deliberately noisy documents |
| `k` | not applicable | the context window - it decides what the model can see *and* what it can out-vote |
| Poisoning | impossible | one keyword-stuffed page can decide hop 1 |

The mock collection is a real, deterministic vector index: TF-IDF with sub-linear term
frequency, smoothed IDF, L2 normalisation and cosine similarity. Documents carry metadata
(`value`, `confidence`, `source`, `tier`) exactly like a Chroma collection would, and the
verifier weighs that metadata when it audits a claim.

It is also **persistent**. The first run writes the index to `chroma_db/trivia_multihop/`:

```
chroma_db/trivia_multihop/
  manifest.json    collection name, format version, document count, corpus hash
  documents.json   the 25 documents with their metadata
  vectors.json     the IDF table and every document vector
```

On every later run the store is **reused** instead of being re-embedded - the manifest's
corpus hash is compared against the corpus, and a changed corpus (or a click on *Rebuild
vector index*) rebuilds it. The settings menu shows the store path and whether the index was
loaded from disk or rebuilt. The vectors survive the round-trip bit-for-bit, so a reloaded
index ranks documents exactly like a fresh one.

### The three agents (Unit 4)

**Planner** – `planner.py` recognises the five canonical question shapes and otherwise
falls back to a BFS over the fact graph, grounding every entity mentioned in the question
(through the alias table as well). Each hop is an `(attribute, anchor, expected entity
type)` triple; later hops consume the *bridge entity* produced by earlier hops.

Candidate chains are scored on four terms: does the question signal this attribute (the
trigger words, e.g. `mayor`, `largest city`), does the final value have the answer type
the question implies (`Who…` → a person), how long is the chain, and is the hop backed by
a curated fact. A hop whose *bridge* does not have the entity type the next hop needs is
discarded before it is ever executed.

The planner will also propose a hop the curated dictionary has no fact for, because the
attribute *schema* allows it (`mayor` of a city) - the retriever then decides whether a
document supports it. That is exactly the stale-web-page case the verifier exists to
catch. If the question asks for a relation the schema does not model at all
(`population`), the planner refuses to substitute a different fact.

**Researcher** – `researcher.py` runs the loop for real:

```
Thought  ->  Action (tool call)  ->  Observation  ->  Thought  ->  ...
```

It stops in exactly one place, `finish_condition()`:

```python
if hop_failed:              return True, "MISSING_INFORMATION"
if resolved_hops >= total:  return True, "ALL_HOPS_RESOLVED"
if actions_taken >= max:    return True, "HOP_CAP_REACHED"
```

**Verifier** – `verifier.py` re-reads the evidence and runs four checks per hop:

| Check | Question it answers |
|---|---|
| `chain_type` | does every bridge entity have the entity type the next hop needs? |
| `evidence_support` | is the value backed by a high-authority document (confidence ≥ 0.7)? |
| `context_conflict` | does a stricter re-retrieval with a wider context out-vote it? |
| `answer_type` | does the final answer have the type the question asked for? |

A failing check produces a `REJECTED` verdict plus a *repair* - the alternative value with
the strongest support - and the researcher re-runs the chain with the corrected bridge.

### What is mocked and what is real

* **Real**: the ReAct control flow, the hop cap, the stop condition, the dictionary, the
  vector index, the ranking, the context-window effects, the verifier's checks, the repair
  loop, session memory.
* **Mocked**: the language. `llm.py` replaces the LLM with templates for the *Thought*
  strings plus a deterministic context-reading policy (`exact` / `greedy` / `majority`).
  Swapping in a real LLM means replacing `MockLLM.thought_for` / `MockLLM.select` and
  nothing else.

---

## 3. The colour palette & design language

The canvas is pure white. Every surface is separated by a 1px silver hairline and a very
soft shadow, and the deep purple is used as an *accent*, never as a wall of colour:

| Colour | Role |
|---|---|
| `#FFFFFF` white | the app canvas, the settings popover, and every card surface |
| `#722F99` deep purple | the title, key text (agent names, the final answer), the active tab underline, primary buttons, the small kicker dot, and the 3px left rules that mark Planner/Verifier output |
| `#C5C1C1` silver | 1px borders, dividers, inactive tab text, secondary helper text, the Observation blocks |
| `#FEE7C8` pale peach | the soft agent cards and the Thought bubbles in the trace |
| `#FF9292` soft red | the Action bubbles, the poisoned hop, a rejected verdict, the missing-information case, the hallucination badge |

The design rules the stylesheet follows:

* **Header** - a compact white navigation bar with the brand mark on the left and a gear
  button on the right, over a soft peach page header. The title is purple, the subtitle is
  secondary ink, and a small purple dot sits next to the kicker.
* **Agent cards** - 1px silver border, a 3px coloured top rule (purple for Planner and
  Verifier, silver for Researcher, soft red when something went wrong), a very soft peach
  fill, `padding: 1.5rem` and `box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05)`.
* **Statuses** - `CONFIRMED`, `ALL_HOPS_RESOLVED`, `REJECTED` and friends are rounded pill
  badges (999px radius, 10px type) rather than raw uppercase text: neutral silver with
  dark text when good, soft red with dark text when bad, a purple tint for accents.
* **Tabs** - no fills. Inactive tabs are secondary ink with a hover to purple; the active
  tab is bold purple with a 2px purple bottom border.
* **Trace** - each step is a white card with a hairline; inside it the Thought bubble is
  peach with a purple left rule, the Action bubble is a soft-red tint, and the Observation
  bubble is a silver tint.
* **Widgets** - the settings popover is white with a silver hairline and a soft shadow; the
  dropdown, number field, slider and buttons are minimal and native, with a purple focus
  ring and a purple slider thumb.


---

## 4. Tests

```bash
python tests/behaviour.py   # asserts the demo behaviours documented above
python tests/smoke.py       # engine: every scenario x mode x k, printed traces
python tests/app_test.py    # head-less Streamlit render: idle -> click -> result -> change
python tests/preview.py     # writes preview.html - a static snapshot of the whole UI
```

`preview.html` is handy for reviewing the layout without starting a server.
