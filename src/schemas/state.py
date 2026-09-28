"""CMN-C1-735 — Agent state (AI Agent Evaluation Dataset Lineage & Contamination Q&A).

ADR-005: State is a flat TypedDict — never a validation/BaseModel instance.
LangGraph checkpoints use msgpack serialization; such model objects cause silent
corruption. Extend AgentState with agent-specific fields only. Complex fields are
stored as JSON strings (``NotRequired[str]`` + ``# JSON:``) for msgpack safety;
nodes ``json.dumps`` on write / ``json.loads`` on read.

S-5 / State Safety: no credentials, secrets, PII, or model weights in State. The
agent answers *how to assess* lineage & contamination — it never emits raw
secrets; guidance is retrieval-grounded and cited (S-3 / S-5).

All agent-specific fields are NotRequired (populated progressively; absent at
empty-start invoke — only user_input is caller-provided).
"""

from __future__ import annotations


from framework.schemas.agent_state import AgentState


class State(AgentState):
    """Agent state for the eval-dataset lineage & contamination Q&A workflow."""

    # ── pre_process (S-1 validated request) ─────────────────────────────────
    validated_query: str  # NFKC-normalised, injection-screened question
    query_context: str  # JSON: {dataset_hint, benchmark_hint, ...} caller context (read-only)

    # ── main composite (classify → retrieve → checks → remediation → answer) ─
    classified_topics: str  # JSON: [{topic, confidence}] — TopicClassify
    retrieved_passages: str  # JSON: [{doc_ref, topic, source, method_type, text, score}] — KBRetrieve
    retrieval_hit_count: int  # total KB records retrieved (0 → out-of-scope safe answer)
    recommended_checks: str  # JSON: [{method_type, topic, check, doc_ref}] — CheckMatch
    remediation_steps: str  # JSON: [{step, doc_ref}] — RemediationAssemble (grounded)
    assembled_answer: str  # cited guidance answer (every claim ends with an inline [<doc_ref>])
    citations: str  # JSON: [{marker, source, doc_ref}]

    # ── post_process (S-3 gate + S-4 audit) ──────────────────────────────────
    disclaimer: str  # "advisory guidance; final contamination judgement is a human decision"
    formatted_output: str  # JSON: final response envelope (answer + checks + citations)
    audit_logged: bool  # True once the terminal audit event is emitted

    # ── degraded-path signalling (SUCCESS + error_code, never status=ERROR) ──
    error_code: str  # INPUT_EMPTY | INPUT_TOO_LONG | INJECTION_REJECTED | CITATION_INCOMPLETE
    error_message: str  # operator-facing detail (no secrets)
