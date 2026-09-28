"""CMN-C1-735 — deterministic domain services (no framework imports).

EvalDatasetKB: a seeded knowledge base for **AI agent evaluation-dataset lineage
& contamination** Q&A. It spans four topic areas — contamination detection,
dedup / decontamination methods, benchmark leakage, dataset lineage / provenance
tracking, canary handling, and documentation/governance standards.

Retrieval is fully **deterministic** (keyword / tag scoring + KB composition —
NO LLM anywhere: config/agent.yaml declares no model, pyproject declares no LLM
dependency, and no node calls an LLM). Every answer is grounded in KB passages
and carries an inline citation, so guidance is auditable and reproducible.

S-5 / State Safety: the agent answers *how to assess* lineage & contamination;
it never emits raw credentials or dataset secrets. A defensive redactor replaces
any credential-shaped token before it can reach the output. Credential-shaped
detection patterns are assembled by string concatenation so no credential-shaped
literal is committed to source (S-5 / gate-credential-scan).
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

# ── seeded evaluation-dataset lineage & contamination KB ──────────────────────
# Each record:
#   {doc_ref, topic, source, tags, method_type, text, remediation}
# method_type ∈ {detection, prevention, documentation, tracking}
KB: list[dict[str, Any]] = [
    {
        "doc_ref": "NGRAM-OVERLAP-001",
        "topic": "contamination-detection",
        "source": "GPT-3 n-gram contamination analysis (Brown et al. 2020)",
        "tags": ["contamination", "ngram", "overlap", "detection", "train-test"],
        "method_type": "detection",
        "text": "Flag test-set contamination by measuring n-gram (e.g. 13-gram) overlap between each "
        "evaluation example and the training corpus; examples above the overlap threshold are "
        "marked as potentially contaminated.",
        "remediation": "Run the n-gram overlap scan over the training corpus, quarantine flagged eval "
        "examples, and report the per-benchmark contamination rate.",
    },
    {
        "doc_ref": "SUBSTRING-MATCH-002",
        "topic": "contamination-detection",
        "source": "Exact substring / hashing contamination scan",
        "tags": ["contamination", "substring", "hashing", "detection", "exact-match"],
        "method_type": "detection",
        "text": "Fast contamination scans hash normalized eval strings and probe them against a hashed "
        "index of the training corpus for exact / near-exact substring matches.",
        "remediation": "Add a substring/hash contamination scan as a CI gate that runs before any new "
        "training corpus is admitted.",
    },
    {
        "doc_ref": "EMBED-SIM-003",
        "topic": "contamination-detection",
        "source": "Semantic near-duplicate contamination detection",
        "tags": ["contamination", "embedding", "semantic", "detection", "near-duplicate"],
        "method_type": "detection",
        "text": "Beyond exact match, semantic (embedding-similarity) near-duplicate detection catches "
        "paraphrased leakage; pairs above a cosine-similarity threshold are surfaced for review.",
        "remediation": "Threshold embedding similarity, route borderline pairs to manual review, and record "
        "the decision so the contamination judgement is auditable.",
    },
    {
        "doc_ref": "MINHASH-DEDUP-004",
        "topic": "dedup-method",
        "source": "MinHash / LSH near-dedup at corpus scale",
        "tags": ["dedup", "minhash", "lsh", "decontamination", "scale"],
        "method_type": "prevention",
        "text": "MinHash + LSH near-deduplication removes duplicated and near-duplicated documents across "
        "a large corpus (e.g. web-scale crawls) before training, shrinking the contamination surface.",
        "remediation": "Build the dedup pipeline before training and document the dedup coverage (fraction "
        "of documents removed) in the dataset lineage record.",
    },
    {
        "doc_ref": "HELDOUT-HYGIENE-005",
        "topic": "benchmark-leakage",
        "source": "Held-out test-set hygiene",
        "tags": ["leakage", "held-out", "hygiene", "prevention", "split-isolation"],
        "method_type": "prevention",
        "text": "Held-out test-set hygiene keeps evaluation splits quarantined from training: never train on "
        "eval splits, isolate them behind access controls, and canary-check before release.",
        "remediation": "Enforce split isolation in the data pipeline and gate eval-set release on a "
        "contamination + canary check.",
    },
    {
        "doc_ref": "BENCH-LEAK-006",
        "topic": "benchmark-leakage",
        "source": "Public-benchmark leakage into web-scraped corpora",
        "tags": ["leakage", "benchmark", "web-scrape", "detection", "time-cutoff"],
        "method_type": "detection",
        "text": "Public benchmarks (e.g. reasoning / knowledge suites) leak into web-scraped training data "
        "verbatim; leakage is estimated by matching benchmark items against the corpus and by "
        "comparing scores on pre- vs post-cutoff splits.",
        "remediation": "Prefer private / freshly-collected test splits and time-based cutoffs so a benchmark "
        "cannot have been seen during training.",
    },
    {
        "doc_ref": "CANARY-GUID-007",
        "topic": "canary",
        "source": "BIG-bench canary GUID convention",
        "tags": ["canary", "guid", "exclusion", "prevention", "benchmark"],
        "method_type": "prevention",
        "text": "A canary GUID string is embedded in a benchmark so data pipelines and models can detect the "
        "benchmark and exclude it from training; presence of the canary in a corpus is direct "
        "evidence of contamination.",
        "remediation": "Honor canary strings: scan corpora for known canaries and exclude canary-marked "
        "data from training splits.",
    },
    {
        "doc_ref": "DVC-LINEAGE-008",
        "topic": "lineage-provenance",
        "source": "Data version control + lineage graph",
        "tags": ["lineage", "provenance", "versioning", "tracking", "reproducibility"],
        "method_type": "tracking",
        "text": "A lineage graph versions each dataset and records the transformations (source → filtering → "
        "dedup → eval split) so an evaluation result can be traced back to an exact, pinned dataset "
        "state for audit and reproducibility.",
        "remediation": "Version datasets, record the transformation lineage, and pin the eval-set commit "
        "referenced by every reported metric.",
    },
    {
        "doc_ref": "DATASHEET-009",
        "topic": "governance-standard",
        "source": "Datasheets for Datasets (Gebru et al.)",
        "tags": ["documentation", "datasheet", "provenance", "governance", "standard"],
        "method_type": "documentation",
        "text": "A datasheet documents a dataset's motivation, composition, collection process, and "
        "recommended uses, giving downstream evaluators the provenance needed to judge contamination "
        "and fitness.",
        "remediation": "Publish a datasheet per evaluation dataset covering provenance, collection, and "
        "known contamination caveats.",
    },
    {
        "doc_ref": "CROISSANT-010",
        "topic": "governance-standard",
        "source": "Croissant / Data Cards machine-readable metadata",
        "tags": ["documentation", "croissant", "data-card", "metadata", "lineage"],
        "method_type": "documentation",
        "text": "Croissant / Data Cards attach machine-readable metadata (fields, license, lineage) to a "
        "dataset so lineage and licensing can be validated automatically across a catalog.",
        "remediation": "Attach Croissant / Data Card metadata to each eval dataset so lineage and license "
        "checks can be automated in the catalog.",
    },
]

_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "contamination-detection": (
        "contamination",
        "contaminate",
        "overlap",
        "leak",
        "leakage",
        "train-test",
        "train test",
        "detect",
        "n-gram",
        "ngram",
        "substring",
        "duplicate",
        "similarity",
    ),
    "dedup-method": ("dedup", "deduplicat", "decontaminat", "minhash", "lsh", "duplicate", "clean"),
    "benchmark-leakage": (
        "benchmark",
        "leak",
        "leakage",
        "held-out",
        "held out",
        "holdout",
        "test set",
        "test-set",
        "cutoff",
        "memoriz",
    ),
    "lineage-provenance": ("lineage", "provenance", "version", "trace", "reproducib", "audit", "origin"),
    "canary": ("canary", "guid", "exclusion marker"),
    "governance-standard": (
        "datasheet",
        "data card",
        "data-card",
        "croissant",
        "metadata",
        "document",
        "documentation",
        "governance",
        "standard",
        "license",
    ),
}

# credential-shaped patterns assembled by concatenation (S-5: no literal in source)
_SK = "sk-"
_AKIA = "AKIA"
_JWT = "eyJ"
_BEARER = "Bearer "
_CRED_RE = re.compile(
    _SK
    + r"[A-Za-z0-9]{12,}|"
    + _AKIA
    + r"[0-9A-Z]{12,}|"
    + _JWT
    + r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}|"
    + _BEARER
    + r"[A-Za-z0-9._-]{16,}"
)
_REDACTED = "<REDACTED:credential>"

# ── PII / identifier hygiene ─────────
# NO syntactic character-class allowlist (a space/symbol-free name — Alice /
# John.Smith / TaroYamada — would slip through one) and NO syntactic passthrough (a
# caller value merely SHAPED like a surrogate — `dataset:deadbeef` / `benchmark:deadbeef`
# — must NOT be trusted). Identifiers are tokenized UNCONDITIONALLY (below): a forged
# surrogate is re-hashed, never passed through, so a caller can never forge an internal
# join key.
# Comprehensive S-3 whole-report redactor patterns (defense-in-depth).
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9\-]{1,63}(?:\.[A-Za-z0-9\-]{1,63}){0,3}\.[A-Za-z]{2,24}")
_MYNUMBER_RE = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")  # JP My-Number (12 digits)
_PHONE_RE = re.compile(r"\+\d[\d\s\-]{7,17}\d|\b0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4}\b")
# JP company forms + EN suffixes (bare "Co" excluded to avoid over-redaction).
_JP_COMPANY_RE = re.compile(
    r"[\wぁ-んァ-ヶ一-龠ー]{1,40}?(?:株式会社|有限会社|合同会社)"
    r"|(?:株式会社|有限会社|合同会社)[\wぁ-んァ-ヶ一-龠ー]{1,40}"
)
_EN_COMPANY_RE = re.compile(r"\b(?:[A-Z][A-Za-z0-9&.\-]*\s+){1,4}(?:Inc|Corp|Corporation|Ltd|LLC|GmbH|PLC|KK)\b\.?")


def tokenize_identifier(value: str, kind: str) -> str:
    """Deterministically tokenize a caller-supplied identifier/reference to an opaque
    surrogate ``<kind>:<sha8>`` — **unconditionally, with no syntactic passthrough**.
    No character-class allowlist is used: a space/symbol-free name (``Alice`` /
    ``John.Smith`` / ``TaroYamada``) would otherwise pass through un-tokenized and leak.
    A caller value merely *shaped* like a surrogate (``dataset:deadbeef`` /
    ``benchmark:deadbeef``) is likewise re-hashed rather than trusted, so a caller can
    never forge an internal join key. Same input → same token (referential integrity);
    identifiers are resolved exactly once at S-1 (pre_process). This is a privacy measure
    only; no surrogate→raw rejoin map is ever kept."""
    digest = hashlib.sha256((value or "").strip().encode("utf-8")).hexdigest()[:8]
    return f"{kind}:{digest}"


def redact_pii(text: str) -> str:
    """S-3 whole-report redactor (defense-in-depth): credential + email + My-Number +
    phone + JP/EN company name. Deterministic; runs on the serialized envelope after
    build (the disclaimer carries no PII, so it is unaffected)."""
    if not text:
        return text
    out = _CRED_RE.sub(_REDACTED, text)
    out = _EMAIL_RE.sub("<REDACTED:email>", out)
    out = _MYNUMBER_RE.sub("<REDACTED:my-number>", out)
    out = _PHONE_RE.sub("<REDACTED:phone>", out)
    out = _JP_COMPANY_RE.sub("<REDACTED:org>", out)
    out = _EN_COMPANY_RE.sub("<REDACTED:org>", out)
    return out


class EvalDatasetKB:
    """Deterministic classification + retrieval + guidance assembly over the seeded KB."""

    @staticmethod
    def classify_topics(query: str) -> list[dict[str, Any]]:
        """Identify which lineage/contamination topics the query touches (keyword match)."""
        q = (query or "").lower()
        hits: list[dict[str, Any]] = []
        for topic, keywords in _TOPIC_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in q)
            if score:
                hits.append({"topic": topic, "confidence": round(min(1.0, 0.5 + 0.1 * score), 2)})
        hits.sort(key=lambda h: -h["confidence"])
        return hits

    @staticmethod
    def retrieve(query: str, topics: list[dict[str, Any]], top_k: int = 6) -> list[dict[str, Any]]:
        """Read-only deterministic retrieval. A 0-hit result is NOT an error."""
        q = (query or "").lower()
        topic_names = {t["topic"] for t in topics}
        scored: list[tuple[int, dict[str, Any]]] = []
        for rec in KB:
            score = 0
            if rec["topic"] in topic_names:
                score += 5
            score += sum(1 for t in rec["tags"] if t in q)
            if score:
                scored.append((score, rec))
        scored.sort(key=lambda x: -x[0])
        out = []
        for score, rec in scored[:top_k]:
            out.append(
                {
                    "doc_ref": rec["doc_ref"],
                    "topic": rec["topic"],
                    "source": rec["source"],
                    "method_type": rec["method_type"],
                    "text": rec["text"],
                    "score": score,
                }
            )
        return out

    @staticmethod
    def recommended_checks(retrieved: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Group retrieved passages into the applicable checks / practices by method_type."""
        out = []
        seen: set[str] = set()
        for r in retrieved:
            key = f"{r['method_type']}:{r['doc_ref']}"
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "method_type": r["method_type"],
                    "topic": r["topic"],
                    "check": r["text"].split(";")[0].strip(),
                    "doc_ref": r["doc_ref"],
                }
            )
        return out

    @staticmethod
    def remediation_steps(retrieved: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Assemble recommended remediation / mitigation steps from KB records (grounded)."""
        out = []
        seen: set[str] = set()
        for r in retrieved:
            rec = next((k for k in KB if k["doc_ref"] == r["doc_ref"]), None)
            if not rec or rec["doc_ref"] in seen:
                continue
            seen.add(rec["doc_ref"])
            out.append({"step": EvalDatasetKB.redact(rec["remediation"]), "doc_ref": rec["doc_ref"]})
        return out

    @staticmethod
    def redact(text: str) -> str:
        """S-5: replace any real credential-shaped token with a placeholder marker."""
        return _CRED_RE.sub(_REDACTED, text or "")


def contains_credential(text: str) -> bool:
    """True if the text contains a real credential-shaped token (S-5 self-check)."""
    return bool(_CRED_RE.search(text or ""))
