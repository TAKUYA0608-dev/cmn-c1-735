# Template Design Specification — CMN-C1-735

> **Stage ② design-only document.** This MR ships design artifacts only
> (docs/02 + `src/schemas/state.py` + the framework-compliance test). The
> node/graph/service/test implementation lands in the Stage ③ implementation MR
> (plan in *Open Items* below), where it has been prototyped and verified locally.

## Position in AgentCore Architecture

- **Template ID**: CMN-C1-735 (Cat 1 / CMN)
- **Agent Class**: `EvaluationDatasetLineageContaminationAgent`
- **L1 Base**: `AgentBaseGraph` (L1 direct inheritance; per 2026-05-18 L2 deprecation) — not
  `AutonomousBaseGraph` (fixed pipeline, no autonomous loop)
- **Pattern**: Cat 1 composite — the `main` slot is a single composite `FunctionNode`
  that orchestrates 5 capability sub-steps via `sub.execute(state)` (same pattern as
  sibling templates). `VectorRAGAgent` is referenced only
  as a *pattern* (KB retrieval), not a base class.
- **Capability**: advisory Q&A on **AI-agent evaluation-dataset lineage & contamination** —
  given a technical question, classify the lineage/contamination topic, retrieve grounded
  passages from a seeded knowledge base (contamination detection / dedup & decontamination /
  benchmark leakage / dataset lineage & provenance / canary handling / documentation
  standards), match the applicable checks, assemble grounded remediation steps, and return a
  **cited** answer. Read-only; deliverable is advisory; the final contamination judgement is a
  human decision (HumanGate).

## Determinism (no LLM)

The template is **fully deterministic** — classification and retrieval use keyword/tag scoring
and KB composition only. `config/agent.yaml` declares no model, `pyproject.toml` declares no
LLM dependency, and no node calls an LLM. Every answer is grounded in KB passages and cited, so
guidance is reproducible and auditable.

## Architecture Overview

### Node Configuration

```
START → initialize → pre_process → main → {route} → post_process → finalize → END
                     (QueryNormalize)  (composite)     (S-3 cite + S-4 audit)
```

| Slot | Class | required_trust_level | Responsibility |
|---|---|---|---|
| pre_process | `QueryNormalizeNode(FunctionNode)` | `VERIFIED_EXTERNAL` | S-1: NFKC / injection screen / size cap on the question. Rejections return **degraded SUCCESS + error_code** with the request body discarded (never `status=ERROR` — post_process must always run). **Whitelist-by-construction**: only the allowed caller hints (`dataset_hint`, `benchmark_hint`) are projected into `query_context`, each **tokenized unconditionally** to an opaque surrogate `<kind>:<sha8>` (a syntactic character-class allowlist is *not* used — it would leak a space/symbol-free name like `Alice`/`John.Smith`/`TaroYamada`; only an already-minted `<kind>:<sha8>` passes through, for idempotency); every other caller field is dropped; the raw `user_input` is cleared as early as possible (input minimization) |
| main | `MainNode(FunctionNode)` — composite | `VERIFIED_EXTERNAL` | Instantiates the 5 sub-nodes in `__init__` (`self._seq`), runs them via `sub.execute(state)`; owns the single S-2/S-3/S-4 boundary; emits `lineage_answer_assembled` (S-4) |
| post_process | `ResponseValidateNode(FunctionNode)` | `VERIFIED_EXTERNAL` | S-3: **fail-closed citation-completeness** (a grounded, hit>0 answer that could not be cited is **blocked** → `needs_review` + `error_code=CITATION_INCOMPLETE`, body withheld, `response_citation_blocked` S-4 event) + **whole-report PII redactor** (credential / email / phone / My-Number / JP+EN company) over the serialized envelope + mandatory advisory disclaimer + terminal `agent_invoke_complete` audit (S-4). Runs on the degraded path too (carrying `error_code`) and always sets `audit_logged`. Output is whitelist-by-construction (KB-derived deliverable only — no caller field is echoed) |

Composite `main` sub-steps (called via `sub.execute(state)` — they do NOT appear in
`node_history`; each declares `required_trust_level` and self-skips on `error_code`; each
emits an S-4 event on every path including the skip guard):

| # | Sub-node | Type | Logic |
|---|---|---|---|
| 1 | `TopicClassifyNode` | deterministic | Classify the question onto the KB topic taxonomy (keyword match) |
| 2 | `KBRetrieveNode` | deterministic (RAG) | Retrieve top-k grounded passages for the topics; **read-only**; 0-hit is not an error → out-of-scope safe answer |
| 3 | `CheckMatchNode` | deterministic | Group retrieved passages into applicable checks/practices by `method_type` (detection / prevention / documentation / tracking) |
| 4 | `RemediationAssembleNode` | retrieval-grounded | Assemble recommended remediation/mitigation steps **from KB records only** — no free LLM generation |
| 5 | `AnswerAssembleNode` | deterministic | Assemble the cited `assembled_answer` (+ citations); 0-hit → in-scope out-of-scope safe answer |

### Data Flow

```
[Caller: AI/ML evaluation engineer / dataset governance owner]
  user_input (NL question) ─→ pre_process: validate → validated_query / query_context
  ─→ main composite:
       TopicClassify       → classified_topics
       KBRetrieve          → retrieved_passages, retrieval_hit_count  (0 → out-of-scope safe answer)
       CheckMatch          → recommended_checks
       RemediationAssemble → remediation_steps (grounded, cited)
       AnswerAssemble      → assembled_answer, citations
  ─→ post_process: citation gate + defensive redaction + disclaimer → formatted_output, audit_logged
[Output: cited guidance + recommended checks + remediation steps + advisory disclaimer]
```

Degraded paths (`INPUT_EMPTY` / `INPUT_TOO_LONG` / `INJECTION_REJECTED`): the node returns
**`status=SUCCESS` + `error_code`** with the body discarded; downstream sub-nodes self-skip,
post_process still audits (carrying the `error_code`) and returns an out-of-scope safe envelope.
(Rationale: under the platform framework `status=ERROR` routes directly to finalize, skipping
S-3/S-4 — verified on the platform.) A **0-hit retrieval is NOT a degraded path** — it routes to
an in-scope "insufficient grounding / out-of-scope" safe answer (no hallucinated advice).

### State Definition

See `src/schemas/state.py` (this MR). Flat TypedDict extending `AgentState`; complex fields are
`NotRequired[str]` JSON strings (ADR-005 msgpack safety) with `# JSON:` shape comments. **No
credentials, secrets, PII, or dataset contents in state** (S-5) — guidance is placeholder/citation-only.

## Framework Utilization

### Shared Components Used

- `framework.graph.agent_base_graph.AgentBaseGraph` — outer graph (L1 direct)
- `framework.nodes.function_node.FunctionNode` — all nodes (S-2/S-3 `@final` gates + `_extra_*` hooks)
- `framework.schemas.trust_level.TrustLevel` — `required_trust_level: ClassVar` on every node
- `shared.utils.audit_logger.emit_trace_event` — S-4 domain events (canonical import; `src.utils.audit` fallback shim, same idiom as server.py)

### Composition Pattern

Cat 1 composite: `MainNode.__init__` builds `self._seq = [TopicClassify, KBRetrieve, CheckMatch,
RemediationAssemble, AnswerAssemble]`; `execute()` folds `sub.execute(working)` deltas and returns
changed keys + `status=AgentStatus.SUCCESS.value`. Registry alias
`EvaluationDatasetLineageContaminationAgent = Graph` + `src/graph/__init__.py` export
(config/agent.yaml `class:` resolution).

## Import Isolation Confirmation

- No `agenticstar` / Level-0 imports anywhere in `src/` (PB-4)
- Nodes import `framework.*` + `shared.*` + `src.*` only
- `EvalDatasetKB` service is pure Python (deterministic, no external calls at test time)

## Design Decision Record

| # | Decision | Rationale |
|---|---|---|
| D-01 | Cat 1 composite (FunctionNode-in-main), not GraphNode | Single capability (lineage/contamination advisory Q&A); the 5 sub-steps are facets of one retrieve-answer pipeline, not a business workflow |
| D-02 | Deterministic (keyword/tag scoring + KB composition), no LLM | Reproducible, auditable guidance; grounded citations with no hallucinated advice |
| D-03 | Degraded paths return `SUCCESS + error_code` (body discarded); 0-hit is an in-scope safe answer | Platform framework routes `ERROR` to finalize, skipping post_process S-3/S-4; 0-hit must not hallucinate |
| D-04 | Injection/oversize rejected at `execute()` (degraded), body discarded | Injection body is never processed; the terminal S-4 audit carries the reject `error_code` so it is provable on the invoke path |
| D-05 | `required_trust_level = VERIFIED_EXTERNAL` on all nodes | Matches `config/agent.yaml`; satisfies the S-1 CI gate (`gate-trust-level-check`) |
| D-06 | S-4 `emit_trace_event` in **every** node's `execute()` (incl. sub-nodes and skip guards) | TC-05: every execute() path emits ≥1 domain event (learned from a sibling template's S-4 findings) |
| D-07 | Final contamination judgement is a human decision (HumanGate); the agent is advisory/read-only | Data-governance boundary — the agent surfaces grounded guidance, humans decide dataset actions |
| D-08 | S-3 citation-completeness is **fail-closed** (grounded-but-uncited → `needs_review` + `CITATION_INCOMPLETE`, body withheld) | An ungrounded/uncited "answer" is unsafe to surface as guidance; block it for human review rather than flag-and-pass |
| D-09 | Caller inputs are whitelist-by-construction: identifiers **tokenized unconditionally** to opaque surrogates (no syntactic allowlist — space/symbol-free names would leak), extra fields dropped, output is KB-derived only; S-3 whole-report PII redactor (credential/email/phone/My-Number/JP+EN company) as defense-in-depth | No caller PII survives into State or output; deterministic tokenization preserves referential integrity |

## Open Items (Stage ③ implementation plan)

Lands in the Stage ③ implementation MR (already prototyped locally):

1. `src/nodes/` — `pre_process_node.py` (`QueryNormalizeNode`), composite `main_node.py` + 5 sub-node modules, `post_process_node.py` (`ResponseValidateNode`) — all rtl-declared config-free `execute(self, state)`, S-4 emit on each path
2. `src/services/service.py` — `EvalDatasetKB` (seeded lineage/contamination passages, topic taxonomy, remediation templates), defensive credential redactor
3. `src/graph/graph.py` — register_nodes + `EvaluationDatasetLineageContaminationAgent = Graph` alias + `__init__` export
4. `config/agent.yaml` — id/category/class wiring (`gate-cat-consistency`)
5. `tests/` — unit (per sub-node + services + S-5 + TC-05), integration (composed pipeline + real `Graph().invoke()` incl. degraded / injection / oversize / 0-hit paths)
6. `docs/03_test_spec.md` — TC/PB matrix (incl. TC-05 per-node emit + injection/oversize degraded invoke tests + S-5 no-credential-in-output negative test)
7. `docs/07_operation_guide.md` — KB curation note (change-controlled via engineer MR + review) + advisory/HumanGate operating boundary
