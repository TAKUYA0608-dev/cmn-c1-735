"""CMN-C1-735 — pre_process slot: QueryNormalizeNode (S-1).

Validates + normalizes the NL lineage/contamination question. Rejections
(empty / oversize / injection) return **degraded SUCCESS + error_code** (never
status=ERROR) with the request body discarded, so the composite self-skips and
post_process always runs the S-3/S-4 boundary (out-of-scope safe answer + audit).
Deterministic — no LLM.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.services.service import tokenize_identifier

try:  # S-4 canonical platform logger (PB-1)
    from shared.utils.audit_logger import emit_trace_event
except ImportError:  # local test env without the platform
    from src.utils.audit import emit_trace_event

_MAX_LEN = 5_000
# Only these caller input_context keys are ever projected into State (whitelist-by-
# construction). Each is an identifier → tokenized via the opaque-id allowlist so no
# caller free-text / PII survives. Any other caller field is dropped, never copied.
_CONTEXT_WHITELIST = ("dataset_hint", "benchmark_hint")
_INJECTION = re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions|system\s+prompt\s*:", re.I)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class QueryNormalizeNode(FunctionNode):
    """S-1: validate + normalize the lineage/contamination question."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("error_code"):
            return {}
        raw = state.get("user_input") or ""
        text = str(raw)
        if not text.strip():
            return self._reject(state, "INPUT_EMPTY", "QueryNormalizeNode: question is empty")
        if len(text) > _MAX_LEN:
            return self._reject(state, "INPUT_TOO_LONG", f"QueryNormalizeNode: exceeds {_MAX_LEN} chars")
        if _INJECTION.search(text):
            # injection is rejected here (execute-level degraded); body is discarded.
            return self._reject(state, "INJECTION_REJECTED", "QueryNormalizeNode: prompt-injection pattern rejected")

        normalized = unicodedata.normalize("NFKC", text)
        normalized = _CONTROL.sub("", normalized).strip()
        normalized = re.sub(r"\s+", " ", normalized)
        # Whitelist-by-construction: project only the allowed identifier hints, each
        # tokenized to a safe opaque id (caller free-text / PII never survives).
        ic = state.get("input_context") or {}
        qc = {k: tokenize_identifier(str(ic.get(k)), k.replace("_hint", "")) for k in _CONTEXT_WHITELIST if ic.get(k)}
        emit_trace_event("query_normalized", {"length": len(normalized)}, state)
        return {
            "validated_query": normalized,
            "query_context": json.dumps(qc, ensure_ascii=False),
            "user_input": "",  # earliest-possible raw clear (input minimization)
            "status": AgentStatus.SUCCESS.value,
        }

    @staticmethod
    def _reject(state: dict[str, Any], code: str, message: str) -> dict[str, Any]:
        # degraded SUCCESS + error_code — body discarded, post_process still audits.
        emit_trace_event("query_rejected", {"error_code": code}, state)
        return {
            "error_code": code,
            "error_message": message,
            "validated_query": "",
            "user_input": "",  # earliest-possible raw clear (injection body discarded)
            "status": AgentStatus.SUCCESS.value,
        }
