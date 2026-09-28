"""CMN-C1-735 — post_process slot: ResponseValidateNode. S-3 gate + S-4 audit.

Responsibilities:
  1. S-3 citation completeness — a grounded answer must carry citations.
  2. S-3/S-5 defensive redaction — never emit a raw credential-shaped token.
  3. Mandatory advisory disclaimer (final contamination judgement is a human decision).
  4. S-4 terminal agent_invoke_complete audit — ALWAYS fires (incl. degraded path,
     carrying the error_code so the reject is provable on the invoke path).
Deterministic — no LLM.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.services.service import EvalDatasetKB, redact_pii

try:  # S-4 canonical platform logger (PB-1)
    from shared.utils.audit_logger import emit_trace_event
except ImportError:  # local test env without the platform
    from src.utils.audit import emit_trace_event

_DISCLAIMER = (
    "\n\n---\nAdvisory guidance grounded in the eval-dataset lineage & contamination KB; "
    "verify against current benchmark/dataset documentation. The final contamination "
    "judgement and any dataset action are a human decision (HumanGate)."
)


class ResponseValidateNode(FunctionNode):
    """S-3 citation + defensive redaction + disclaimer + S-4 terminal audit."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # ── degraded / rejected path (injection / oversize / empty): always audit ──
        if state.get("error_code"):
            code = state["error_code"]
            emit_trace_event("agent_invoke_complete", {"validation_status": "out_of_scope", "error_code": code}, state)
            envelope: dict[str, Any] = {
                "answer": (
                    f"Request could not be processed ({code}); handled as an out-of-scope safe "
                    "response with no grounded guidance." + _DISCLAIMER
                ),
                "validation_status": "out_of_scope",
                "error_code": code,
                "citations": [],
                "recommended_checks": [],
            }
            return self._envelope_out(envelope)

        citations = json.loads(state.get("citations") or "[]")
        hit = state.get("retrieval_hit_count", 0) or 0
        retrieved = json.loads(state.get("retrieved_passages") or "[]")
        checks = json.loads(state.get("recommended_checks") or "[]")
        remediation = json.loads(state.get("remediation_steps") or "[]")

        # ── S-3 per-entry citation-completeness (fail-closed) ──
        # A grounded (hit>0) deliverable is presented ONLY when EVERY emitted claim — each retrieved
        # passage, recommended check, AND remediation step — is backed by an authorized top-level
        # {doc_ref, source} citation (truthy source). A partial citation loss — a claim whose doc_ref
        # carries no cited source, OR a top-level citation belonging to a different doc_ref (a non-empty
        # citation list is NOT sufficient) — is BLOCKED: the body is withheld,
        # error_code=CITATION_INCOMPLETE, and a citation_blocked S-4 event fires. (0-hit is an in-scope
        # safe answer, exempt.)
        cited_sources = {c.get("doc_ref"): c.get("source") for c in citations if c.get("source")}
        emitted_claims = retrieved + checks + remediation
        citation_complete = bool(citations) and all(
            c.get("doc_ref") and cited_sources.get(c.get("doc_ref")) for c in emitted_claims
        )
        if hit > 0 and not citation_complete:
            code = state.get("error_code") or "CITATION_INCOMPLETE"
            emit_trace_event("response_citation_blocked", {"error_code": code, "hit_count": hit}, state)
            emit_trace_event(
                "agent_invoke_complete",
                {"validation_status": "needs_review", "error_code": code, "citation_count": 0},
                state,
            )
            envelope = {
                "answer": (
                    "Answer withheld for human review: the grounded guidance could not be cited "
                    "to its source KB records." + _DISCLAIMER
                ),
                "validation_status": "needs_review",
                "error_code": code,
                "citations": [],
                "recommended_checks": [],
            }
            return self._envelope_out(envelope)

        # ── normal path: grounded+cited (passed) or 0-hit (out_of_scope safe answer) ──
        answer = EvalDatasetKB.redact(state.get("assembled_answer") or "")
        validation_status = "out_of_scope" if hit == 0 else "passed"
        answer = answer + _DISCLAIMER

        envelope = {
            "answer": answer,
            "validation_status": validation_status,
            "citations": citations,
            "recommended_checks": checks,
            "remediation_steps": remediation,
        }
        emit_trace_event(
            "agent_invoke_complete",
            {"validation_status": validation_status, "citation_count": len(citations), "disclaimer_present": True},
            state,
        )
        return self._envelope_out(envelope)

    @staticmethod
    def _envelope_out(envelope: dict[str, Any]) -> dict[str, Any]:
        # S-3 whole-report redactor runs on the serialized envelope (defense-in-depth):
        # credential / email / My-Number / phone / JP+EN company. Deliverable content is
        # KB-derived (whitelist-by-construction), so this only ever fires on leaked PII.
        return {
            "formatted_output": redact_pii(json.dumps(envelope, ensure_ascii=False)),
            "disclaimer": _DISCLAIMER.strip(),
            "audit_logged": True,
            "status": AgentStatus.SUCCESS.value,
        }
