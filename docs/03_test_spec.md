# Test Specification — CMN-C1-735

AI Agent Evaluation Dataset Lineage & Contamination Q&A Agent (Cat 1 / CMN).
All tests are deterministic (no LLM, no network).

## Coverage & result summary

- **Coverage**: 90% over `src/` (98% excluding the scaffold-provided `src/api/server.py`,
  which is not unit-tested at this stage — same as the reference Cat 1 template).
- **CI (real `agenticstar-agentcore` wheel)**: all tests pass, including the framework-compliance
  and proof-of-boundary tests.
- **Local (the local SDK stub)**: 42 authored tests pass + PB-7 conditional stubs skipped. Three tests
  are **known the local SDK stub-vs-real-SDK differences** that pass only against the real SDK (they assert
  runtime enforcement the local SDK stub shim does not implement):
  `tests/proof_of_boundary/test_pb_invoke_order.py` (patches `base_node.emit_trace_event`) and
  `tests/unit/test_framework_compliance_tc06_tc07.py` (`@final` gate enforcement). These are
  identical in behavior to the shipped reference templates.

## Unit tests

### `tests/unit/test_main_node.py` — composite MainNode
| ID | Test | Assertion |
|---|---|---|
| MN-01 | trust level | `MainNode.required_trust_level == VERIFIED_EXTERNAL` |
| MN-02 | composes 5 sub-steps | `len(self._seq) == 5` |
| MN-03 | grounded path | contamination question → `retrieval_hit_count > 0`, cited answer |
| MN-04 | degraded skip | `error_code` set → returns `{}` (no grounded body) |
| MN-05 | 0-hit out-of-scope | unknown topic → hit_count 0, no error_code, safe answer, citations `[]` |
| MN-06 | config-free execute | `execute(self, state)` — no `config` param |

### `tests/unit/test_nodes.py` — pre/post nodes, sub-nodes, services, S-5, TC-05
| Group | Coverage |
|---|---|
| TrustLevels | all 7 FunctionNode subclasses declare `VERIFIED_EXTERNAL` |
| QueryNormalize | empty → `INPUT_EMPTY` (degraded SUCCESS, body discarded); oversize → `INPUT_TOO_LONG`; injection → `INJECTION_REJECTED` (body discarded); NFKC normalize; **caller hints tokenized unconditionally to opaque surrogates (incl. space/symbol-free names) + extra caller fields dropped (whitelist-by-construction)**; **earliest raw `user_input` clear**; self-skip on `error_code` |
| Pipeline | grounded contamination-detection / lineage-provenance / dedup / canary retrieval; 0-hit out-of-scope; sub-nodes self-skip on `error_code` |
| PostProcess | degraded (injection/oversize/empty) path audits + carries `error_code` (`out_of_scope`, disclaimer/HumanGate); grounded cited + disclaimer; 0-hit out-of-scope; **grounded-without-citation → fail-closed `needs_review` + `error_code=CITATION_INCOMPLETE` + `response_citation_blocked` emit (body withheld)**; S-5 defensive credential redaction; **S-3 whole-report PII redaction (email/phone/My-Number/company)** |
| TC-05 emit | every node's `execute()` emits ≥1 domain event (7 events); **skip guard path also emits** (`skipped: true`) |
| Services | credential + PII redaction (email/phone/My-Number/JP+EN company); no over-redaction of clean KB text; `tokenize_identifier` **unconditional tokenize** (space/symbol-free names surrogated) + deterministic + idempotent; `contains_credential`; multi-topic classify; empty retrieve on unknown |

### `tests/unit/test_framework_compliance_tc06_tc07.py` (framework-required)
TC-06/TC-07: overriding the `@final` `_security_gate_input` / `_security_gate_output` raises at
class definition (real-SDK enforcement). Copied verbatim from the scaffold mirror.

## Integration tests — `tests/integration/test_end_to_end.py` (real `Graph().invoke()`)
| ID | Test | Assertion |
|---|---|---|
| E2E-01 | grounded invoke | `validation_status == passed`, citations present |
| E2E-02 | out-of-scope invoke | `validation_status == out_of_scope`, citations `[]` |
| E2E-03 | node_history | `[InitializeNode, QueryNormalizeNode, MainNode, ResponseValidateNode, FinalizeNode]` |
| E2E-04 | no credential leak | a real credential-shaped token never appears anywhere in the result |
| E2E-05 | **injection invoke** | injection → `out_of_scope`, `ResponseValidateNode` in node_history (post ran), body discarded, terminal S-4 audit carries `error_code=INJECTION_REJECTED` |
| E2E-06 | **oversize invoke** | oversize → `out_of_scope`, post ran, terminal S-4 audit carries `error_code=INPUT_TOO_LONG` |
| E2E-07 | **citation-incomplete invoke** | grounded-but-uncited (forced) → `needs_review`, body withheld, post ran, terminal S-4 audit carries `error_code=CITATION_INCOMPLETE` |
| E2E-08 | **PII non-leak invoke** | caller hints with space/symbol-free names (`Alice`/`John.Smith`/`TaroYamada`) + phone + extra caller field → none reaches output (unconditional tokenize + whitelist-by-construction + S-3) |

## Proof-of-Boundary (`tests/proof_of_boundary/`)
- PB-2/PB-5 `test_state_safety.py` — State msgpack-safe, no credential fields / prohibited types.
- PB-4 `test_import_isolation.py` — no Level-0 `agenticstar` imports in `src/`.
- `test_pb_invoke_order.py` — S-1 gate → execute order for every node (real-SDK).
- PB-7 `test_pb7_hitl_interrupt_propagation.py` — conditional stub (hitl disabled → skipped).

## Security mapping
- **S-1** injection/oversize screen at `QueryNormalizeNode.execute()` → degraded SUCCESS + `error_code`, body discarded; caller hints tokenized (opaque-id allowlist), extra caller fields dropped (whitelist-by-construction), earliest raw `user_input` clear.
- **S-3** **fail-closed citation-completeness** (grounded-but-uncited → `needs_review` + `CITATION_INCOMPLETE`, body withheld) + whole-report PII redaction (credential / email / phone / My-Number / JP+EN company) + advisory disclaimer at `ResponseValidateNode`.
- **S-4** `emit_trace_event` on every node path (incl. skip guards); terminal `agent_invoke_complete` always fires and carries `error_code` on the degraded / citation-blocked paths; `response_citation_blocked` on the fail-closed path.
- **S-5** no credentials/secrets/PII in State or output; identifiers tokenized; output is whitelist-by-construction (KB-derived only); deterministic KB grounding.
