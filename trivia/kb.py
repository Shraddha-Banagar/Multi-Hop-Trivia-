"""Unit 3 - the retrieval layer.

Two retrieval strategies sit behind one interface:

* ``DictionaryTool``  - an exact ``(attribute, anchor) -> value`` key/value
  lookup. Precise, zero noise, but it only knows the curated facts.
* ``ChromaTool``      - a *mock ChromaDB* collection: documents are embedded
  with a TF-IDF bag-of-words vectoriser, stored in an in-memory index and
  queried with cosine similarity + ``top_k``. The collection deliberately
  contains noisy "web" documents (decoys) so that ``k`` and ranking matter.

Both tools expose the same surface to the ReAct agent, so switching the mode
in the sidebar swaps the *evidence* but never the *control flow*.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# --------------------------------------------------------------------------
# Fact model
# --------------------------------------------------------------------------


@dataclass
class Fact:
    id: str
    subject: str
    attribute: str
    value: str
    subject_type: str
    value_type: str
    text: str
    confidence: float = 0.99
    source: str = "Curated KB"
    decoy: bool = False
    tier: str = "curated"

    def metadata(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "attribute": self.attribute,
            "value": self.value,
            "subject_type": self.subject_type,
            "value_type": self.value_type,
            "confidence": round(self.confidence, 3),
            "source": self.source,
            "tier": self.tier,
            "decoy": self.decoy,
        }


# ``range``  = which entity types the attribute can produce
# ``domain`` = which entity types the attribute can be applied to
# ``words``  = question words that signal this attribute
ATTRIBUTES: Dict[str, Dict[str, Any]] = {
    "capital": {
        "range": {"city"},
        "domain": {"country"},
        "words": ["capital"],
        "query": "{anchor} capital city",
    },
    "mayor": {
        "range": {"person"},
        "domain": {"city"},
        "words": ["mayor", "governor"],
        "query": "{anchor} mayor",
    },
    "largest_city": {
        "range": {"city"},
        "domain": {"country"},
        "words": ["largest city", "biggest city", "most populous"],
        "query": "{anchor} largest city",
    },
    "director": {
        "range": {"person"},
        "domain": {"film", "work"},
        "words": ["director", "directed"],
        "query": "{anchor} film director",
    },
    "birthplace": {
        "range": {"place", "city"},
        "domain": {"person"},
        "words": ["birthplace", "born", "hometown"],
        "query": "{anchor} born birthplace city",
    },
    "location": {
        "range": {"country"},
        "domain": {"landmark", "building", "place", "work", "film"},
        "words": ["located", "location", "country"],
        "query": "{anchor} location country",
    },
    "country": {
        "range": {"country"},
        "domain": {"city", "place", "landmark"},
        "words": ["country", "nation"],
        "query": "{anchor} country",
    },
    "nationality": {
        "range": {"person"},
        "domain": {"person"},
        "words": ["nationality", "national"],
        "query": "{anchor} nationality",
    },
    "country_of_origin": {
        "range": {"country"},
        "domain": {"film", "work"},
        "words": ["origin", "made in"],
        "query": "{anchor} country of origin",
    },
}

# Answer-type expectations inferred from the question wording.
ANSWER_TYPES = {
    "person": {"person"},
    "city": {"city", "place"},
    "place": {"place", "city", "country"},
    "country": {"country"},
}


# --------------------------------------------------------------------------
# The corpus
# --------------------------------------------------------------------------

CURATED_FACTS: List[Fact] = [
    Fact(
        id="f_france_capital",
        subject="France",
        attribute="capital",
        value="Paris",
        subject_type="country",
        value_type="city",
        text="Paris is the capital and largest city of France. The capital of France is Paris.",
    ),
    Fact(
        id="f_paris_mayor",
        subject="Paris",
        attribute="mayor",
        value="Anne Hidalgo",
        subject_type="city",
        value_type="person",
        text="Anne Hidalgo has been the mayor of Paris since 2014. The mayor of Paris is Anne Hidalgo.",
    ),
    Fact(
        id="f_germany_capital",
        subject="Germany",
        attribute="capital",
        value="Berlin",
        subject_type="country",
        value_type="city",
        text="Berlin is the capital and largest city of Germany. The capital of Germany is Berlin.",
    ),
    Fact(
        id="f_australia_capital",
        subject="Australia",
        attribute="capital",
        value="Canberra",
        subject_type="country",
        value_type="city",
        text="Canberra is the capital of Australia. The capital of Australia is Canberra.",
    ),
    Fact(
        id="f_australia_largest",
        subject="Australia",
        attribute="largest_city",
        value="Sydney",
        subject_type="country",
        value_type="city",
        text="Sydney is the largest city in Australia by population. The largest city of Australia is Sydney.",
    ),
    Fact(
        id="f_sydney_country",
        subject="Sydney",
        attribute="country",
        value="Australia",
        subject_type="city",
        value_type="country",
        text="Sydney is a harbour city located in Australia, home of the Sydney Opera House.",
    ),
    Fact(
        id="f_jp_director",
        subject="Jurassic Park",
        attribute="director",
        value="Steven Spielberg",
        subject_type="film",
        value_type="person",
        text="Jurassic Park is a 1993 film directed by Steven Spielberg. The director of Jurassic Park is Steven Spielberg.",
    ),
    Fact(
        id="f_spielberg_birthplace",
        subject="Steven Spielberg",
        attribute="birthplace",
        value="Cincinnati",
        subject_type="person",
        value_type="city",
        text="Steven Spielberg was born in Cincinnati, Ohio. The birthplace of Steven Spielberg is Cincinnati.",
    ),
    Fact(
        id="f_spielberg_nationality",
        subject="Steven Spielberg",
        attribute="nationality",
        value="American",
        subject_type="person",
        value_type="person",
        text="Steven Spielberg is an American filmmaker. The nationality of Steven Spielberg is American.",
    ),
    Fact(
        id="f_eiffel_location",
        subject="Eiffel Tower",
        attribute="location",
        value="France",
        subject_type="landmark",
        value_type="country",
        text="The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France. The Eiffel Tower location is the country France.",
    ),
    Fact(
        id="f_hollywood_location",
        subject="Hollywood Sign",
        attribute="location",
        value="United States",
        subject_type="landmark",
        value_type="country",
        text="The Hollywood Sign is a landmark in Los Angeles, California, United States. The Hollywood Sign location is the country United States.",
    ),
    Fact(
        id="f_usa_capital",
        subject="United States",
        attribute="capital",
        value="Washington, D.C.",
        subject_type="country",
        value_type="city",
        text="Washington, D.C. is the capital of the United States. The capital of the United States is Washington, D.C.",
    ),
    Fact(
        id="f_japan_capital",
        subject="Japan",
        attribute="capital",
        value="Tokyo",
        subject_type="country",
        value_type="city",
        text="Tokyo is the capital and largest city of Japan. The capital of Japan is Tokyo.",
    ),
    Fact(
        id="f_tokyo_country",
        subject="Tokyo",
        attribute="country",
        value="Japan",
        subject_type="city",
        value_type="country",
        text="Tokyo is a city in Japan on the island of Honshu.",
    ),
    Fact(
        id="f_alcatraz_location",
        subject="Alcatraz Island",
        attribute="location",
        value="United States",
        subject_type="landmark",
        value_type="country",
        text="Alcatraz Island is a prison island in San Francisco Bay, California, United States.",
    ),
    Fact(
        id="f_columbus_country",
        subject="Columbus",
        attribute="country",
        value="United States",
        subject_type="city",
        value_type="country",
        text="Columbus is a city in the American state of Ohio, United States.",
    ),
    Fact(
        id="f_ohio_capital",
        subject="Ohio",
        attribute="capital",
        value="Columbus",
        subject_type="country",
        value_type="city",
        text="Columbus is the capital of Ohio. The capital of Ohio is Columbus.",
    ),
    Fact(
        id="f_paris_country",
        subject="Paris",
        attribute="country",
        value="France",
        subject_type="city",
        value_type="country",
        text="Paris is a major city and the seat of government in France.",
    ),
    Fact(
        id="f_berlin_country",
        subject="Berlin",
        attribute="country",
        value="Germany",
        subject_type="city",
        value_type="country",
        text="Berlin is a city located in Germany, in the north-east of the country.",
    ),
    Fact(
        id="f_cincinnati_country",
        subject="Cincinnati",
        attribute="country",
        value="United States",
        subject_type="city",
        value_type="country",
        text="Cincinnati is a city in the U.S. state of Ohio.",
    ),
]

# Noisy "web" documents. These are NOT in the curated dictionary - they only
# exist inside the Chroma collection, which is precisely why switching the
# retrieval mode changes the evidence the agent sees.
NOISY_FACTS: List[Fact] = [
    Fact(
        id="n_eiffel_japan",
        subject="Eiffel Tower",
        attribute="location",
        value="Japan",
        subject_type="landmark",
        value_type="country",
        text=(
            "Eiffel Tower location country. The Eiffel Tower location country is Japan. Eiffel Tower "
            "location country: city Tokyo, country Japan. Book an Eiffel Tower location country tour. "
            "Eiffel Tower location country and Eiffel Tower location country and Eiffel Tower location "
            "country. Cheap Eiffel Tower location country tickets in Japan."
        ),
        confidence=0.30,
        source="TravelForumAggregator",
        decoy=True,
        tier="forum",
    ),
    Fact(
        id="n_eiffel_france_2",
        subject="Eiffel Tower",
        attribute="location",
        value="France",
        subject_type="landmark",
        value_type="country",
        text=(
            "The Eiffel Tower stands in the country of France, in the city of Paris. The Eiffel Tower "
            "location country is France."
        ),
        confidence=0.96,
        source="Wikipedia",
        tier="curated",
    ),
    Fact(
        id="n_berlin_mayor_brandt",
        subject="Berlin",
        attribute="mayor",
        value="Willy Brandt",
        subject_type="city",
        value_type="person",
        text=(
            "Berlin mayor - Willy Brandt served as the mayor of Berlin from 1957 until 1966. Berlin "
            "mayor listing: Willy Brandt, Berlin mayor. The Berlin mayor in that era was Willy Brandt; "
            "Berlin mayor Willy Brandt, mayor of Berlin."
        ),
        confidence=0.34,
        source="CityArchiveBlog",
        decoy=True,
        tier="forum",
    ),
    Fact(
        id="n_jp_cameron",
        subject="Jurassic Park",
        attribute="director",
        value="James Cameron",
        subject_type="film",
        value_type="person",
        text=(
            "James Cameron is the director of Avatar and its sequels, a different blockbuster "
            "director with a very similar film career profile."
        ),
        confidence=0.36,
        source="FilmBlogRoundup",
        decoy=True,
        tier="forum",
    ),
    Fact(
        id="n_paris_cafe",
        subject="Paris",
        attribute="tourism",
        value="Montmartre",
        subject_type="city",
        value_type="place",
        text=(
            "Paris travel guide: the best cafes in Paris, near the Eiffel Tower and the Montmartre "
            "district, with tips for a long weekend in Paris France."
        ),
        confidence=0.42,
        source="TravelGuideBlog",
        decoy=True,
        tier="forum",
    ),
]

ALL_FACTS: List[Fact] = CURATED_FACTS + NOISY_FACTS

ALIASES: Dict[str, str] = {
    "the eiffel tower": "Eiffel Tower",
    "eiffel tower": "Eiffel Tower",
    "eiffel": "Eiffel Tower",
    "hollywood sign": "Hollywood Sign",
    "alcatraz island": "Alcatraz Island",
    "alcatraz": "Alcatraz Island",
    "jurassic park": "Jurassic Park",
    "jurassic park film": "Jurassic Park",
    "united states": "United States",
    "usa": "United States",
    "u.s.": "United States",
    "us": "United States",
    "america": "United States",
    "washington dc": "Washington, D.C.",
    "washington d.c.": "Washington, D.C.",
    "washington": "Washington, D.C.",
    "steven spielberg": "Steven Spielberg",
    "spielberg": "Steven Spielberg",
    "anne hidalgo": "Anne Hidalgo",
    "hidalgo": "Anne Hidalgo",
    "cincinnati": "Cincinnati",
    "sydney": "Sydney",
    "canberra": "Canberra",
    "tokyo": "Tokyo",
    "japan": "Japan",
    "paris": "Paris",
    "berlin": "Berlin",
    "germany": "Germany",
    "france": "France",
    "australia": "Australia",
    "columbus": "Columbus",
    "ohio": "Ohio",
    "will:y brandt": "Willy Brandt",
    "willy brandt": "Willy Brandt",
}

ENTITY_TYPES: Dict[str, str] = {}
for _f in ALL_FACTS:
    ENTITY_TYPES[_f.subject] = _f.subject_type
    ENTITY_TYPES[_f.value] = _f.value_type


def normalize(name: str) -> str:
    """Lower-case, strip articles and punctuation, resolve aliases."""
    s = name.strip().lower()
    s = re.sub(r"^(the|a|an)\s+", "", s)
    s = re.sub(r"[^\w\s.&-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s in ALIASES:
        return ALIASES[s].lower()
    return s


def canonical(name: str) -> str:
    key = normalize(name)
    for alias, target in ALIASES.items():
        if target.lower() == key:
            return target
    return name.strip()


# --------------------------------------------------------------------------
# Mock embedding + vector index
# --------------------------------------------------------------------------


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class MockEmbedding:
    """A tiny deterministic TF-IDF embedder (no external model needed).

    Sub-linear term frequency + smoothed IDF + L2 normalisation gives a
    cosine geometry that behaves like a real sentence-embedding space for
    this kind of factual lookup, while staying 100% offline and instant.
    """

    def __init__(self, corpus: Sequence[str]):
        self.idf: Dict[str, float] = {}
        self.default_idf = 0.0
        self._fit(corpus)

    @classmethod
    def from_state(cls, idf: Dict[str, float], default_idf: float) -> "MockEmbedding":
        """Rebuild an embedder from a persisted IDF table (no re-fitting)."""
        emb = cls.__new__(cls)
        emb.idf = dict(idf)
        emb.default_idf = default_idf
        return emb

    def _fit(self, corpus: Sequence[str]) -> None:
        n_docs = max(1, len(corpus))
        df: Counter = Counter()
        for doc in corpus:
            df.update(set(_tokenize(doc)))
        self.default_idf = math.log(n_docs + 1) + 1.0
        self.idf = {t: math.log((n_docs + 1) / (c + 1)) + 1.0 for t, c in df.items()}

    def encode(self, text: str) -> Dict[str, float]:
        tf = Counter(_tokenize(text))
        vec = {
            t: (1.0 + math.log(c)) * self.idf.get(t, self.default_idf)
            for t, c in tf.items()
        }
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}


def cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(t, 0.0) for t, v in a.items())


class MockChromaCollection:
    """Drop-in stand-in for ``chromadb.Collection``.

    Supports the small subset the agent needs: ``add`` (used at build time),
    ``query(query_texts, n_results)`` returning ids / documents / metadatas /
    distances, and ``count``.

    The collection is *persistent*: :meth:`save` writes the documents, the
    embedding state and the vectors to disk, and :meth:`load` restores them
    without re-embedding anything.  That mirrors what a real ChromaDB
    ``PersistentClient`` does and it is what makes the ``chroma_db/`` folder
    appear on disk the first time the app runs.
    """

    #: bumped whenever the on-disk layout changes
    FORMAT_VERSION = 1

    def __init__(
        self,
        name: str,
        documents: Sequence[Fact],
        embedder: Optional["MockEmbedding"] = None,
        vectors: Optional[Sequence[Dict[str, float]]] = None,
    ) -> None:
        self.name = name
        self.documents: List[Fact] = list(documents)
        self.ids: List[str] = [d.id for d in self.documents]
        if embedder is None:
            embedder = MockEmbedding([d.text for d in self.documents])
        self._embedder = embedder
        if vectors is None:
            vectors = [self._embedder.encode(d.text) for d in self.documents]
        self._vectors: List[Dict[str, float]] = [dict(v) for v in vectors]
        #: where this collection came from: "memory" | "disk" | "built"
        self.source = "memory"
        #: absolute path of the store on disk (None for a pure memory build)
        self.store_path: Optional[str] = None

    # -- chroma-like API ---------------------------------------------------
    def count(self) -> int:
        return len(self.documents)

    def get(self, ids: Optional[Sequence[str]] = None) -> List[Fact]:
        if ids is None:
            return list(self.documents)
        wanted = set(ids)
        return [d for d in self.documents if d.id in wanted]

    def query(
        self,
        query_texts: Sequence[str],
        n_results: int = 4,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[List[Any]]]:
        q_vec = self._embedder.encode(query_texts[0])
        scored: List[Tuple[float, int]] = []
        for idx, vec in enumerate(self._vectors):
            if where and not self._matches(self.documents[idx], where):
                continue
            scored.append((cosine(q_vec, vec), idx))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        top = scored[: max(1, n_results)]
        return {
            "ids": [[self.documents[i].id for _, i in top]],
            "documents": [[self.documents[i].text for _, i in top]],
            "metadatas": [[self.documents[i].metadata() for _, i in top]],
            "distances": [[round(1.0 - s, 4) for s, _ in top]],
            "similarities": [[round(s, 4) for s, _ in top]],
        }

    @staticmethod
    def _matches(fact: Fact, where: Dict[str, Any]) -> bool:
        meta = fact.metadata()
        return all(meta.get(k) == v for k, v in where.items())

    # -- persistence -------------------------------------------------------
    def fingerprint(self) -> str:
        """Hash of the corpus, used to detect a stale store on disk."""
        return _corpus_fingerprint(self.documents)

    def to_records(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": f.id,
                "subject": f.subject,
                "attribute": f.attribute,
                "value": f.value,
                "subject_type": f.subject_type,
                "value_type": f.value_type,
                "text": f.text,
                "confidence": f.confidence,
                "source": f.source,
                "decoy": f.decoy,
                "tier": f.tier,
            }
            for f in self.documents
        ]

    def save(self, directory: Path) -> Path:
        """Write the collection to ``directory`` and return the path."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "documents.json").write_text(
            json.dumps(self.to_records(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (directory / "vectors.json").write_text(
            json.dumps(
                {
                    "idf": self._embedder.idf,
                    "default_idf": self._embedder.default_idf,
                    "vectors": {i: v for i, v in zip(self.ids, self._vectors)},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manifest = {
            "name": self.name,
            "format_version": self.FORMAT_VERSION,
            "embedding": {"type": "tfidf-bow", "version": 1},
            "document_count": self.count(),
            "vocabulary_size": len(self._embedder.idf),
            "corpus_hash": self.fingerprint(),
            "documents": "documents.json",
            "vectors": "vectors.json",
        }
        (directory / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        self.store_path = str(directory)
        return directory

    @classmethod
    def load(cls, directory: Path) -> "MockChromaCollection":
        """Restore a collection previously written by :meth:`save`."""
        directory = Path(directory)
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        records = json.loads((directory / "documents.json").read_text(encoding="utf-8"))
        payload = json.loads((directory / "vectors.json").read_text(encoding="utf-8"))
        facts = [Fact(**record) for record in records]
        embedder = MockEmbedding.from_state(payload["idf"], payload.get("default_idf", 0.0))
        vectors = [payload["vectors"][i] for i in (f.id for f in facts)]
        collection = cls(manifest.get("name", "trivia_multihop"), facts,
                         embedder=embedder, vectors=vectors)
        collection.source = "disk"
        collection.store_path = str(directory)
        return collection


# --------------------------------------------------------------------------
# Indexes
# --------------------------------------------------------------------------

#: Name of the collection inside the local store.
CHROMA_COLLECTION_NAME = "trivia_multihop"

#: Where the mock ChromaDB persists itself (created on first use).
CHROMA_DB_DIR = Path(__file__).resolve().parent.parent / "chroma_db"


def chroma_store_path(
    persist_dir: Optional[Path] = None,
    name: str = CHROMA_COLLECTION_NAME,
) -> Path:
    """Absolute path of the collection folder inside the local store."""
    base = Path(persist_dir) if persist_dir else CHROMA_DB_DIR
    return base / name


def _corpus_fingerprint(facts: Sequence[Fact]) -> str:
    h = hashlib.sha256()
    for f in facts:
        h.update(
            f"{f.id}|{f.subject}|{f.attribute}|{f.value}|{f.text}|"
            f"{f.confidence}|{f.source}|{f.decoy}\n".encode("utf-8")
        )
    return h.hexdigest()


def build_dictionary() -> Dict[str, Fact]:
    """Exact ``attribute|anchor`` -> fact index over the curated facts only."""
    index: Dict[str, Fact] = {}
    for fact in CURATED_FACTS:
        key_sub = f"{fact.attribute}|{normalize(fact.subject)}"
        key_val = f"{fact.attribute}|{normalize(fact.value)}"
        index.setdefault(key_sub, fact)
        index.setdefault(key_val, fact)
    return index


def build_chroma(
    persist_dir: Optional[Path] = None,
    force_rebuild: bool = False,
    name: str = CHROMA_COLLECTION_NAME,
) -> MockChromaCollection:
    """The document index: curated facts + noisy web documents.

    If ``persist_dir`` is given the collection is written to
    ``<persist_dir>/<name>/`` (manifest + documents + vectors).  A store that
    is already on disk is *reused* instead of being rebuilt, unless
    ``force_rebuild`` is set or the corpus has changed.
    """
    store = chroma_store_path(persist_dir, name)
    fingerprint = _corpus_fingerprint(ALL_FACTS)

    if not force_rebuild and (store / "manifest.json").exists():
        try:
            manifest = json.loads((store / "manifest.json").read_text(encoding="utf-8"))
            fresh = (
                manifest.get("format_version") == MockChromaCollection.FORMAT_VERSION
                and manifest.get("corpus_hash") == fingerprint
            )
            if fresh:
                collection = MockChromaCollection.load(store)
                collection.source = "disk"
                collection.store_path = str(store)
                return collection
        except (OSError, ValueError, KeyError, TypeError):
            pass  # a corrupt store is simply rebuilt

    collection = MockChromaCollection(name, ALL_FACTS)
    try:
        collection.save(store)
        collection.source = "built"
    except OSError:
        collection.source = "memory"
    return collection


_CHROMA_CACHE: Dict[str, MockChromaCollection] = {}


def get_chroma(
    persist_dir: Optional[Path] = None,
    force_rebuild: bool = False,
    name: str = CHROMA_COLLECTION_NAME,
) -> MockChromaCollection:
    """Process-wide cached handle on the persisted collection.

    Streamlit re-runs the whole script on every interaction, so the index has
    to be built once per process - otherwise the embeddings are recomputed on
    every click and the ``chroma_db/`` folder never gets a stable identity.
    """
    base = Path(persist_dir) if persist_dir else CHROMA_DB_DIR
    store = chroma_store_path(base, name)
    key = str(store.resolve())
    if force_rebuild or key not in _CHROMA_CACHE:
        _CHROMA_CACHE[key] = build_chroma(base, force_rebuild=force_rebuild, name=name)
    return _CHROMA_CACHE[key]


def reset_chroma_cache() -> None:
    """Drop the cached collection (used by the 'Rebuild index' button)."""
    _CHROMA_CACHE.clear()
