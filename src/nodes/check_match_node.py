"""CheckMatchNode — composite sub-step 3: map retrieved passages to applicable checks.

Deterministic: groups the retrieved KB passages into the recommended contamination
checks / lineage practices by method_type (detection / prevention / documentation /
tracking). No LLM.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.services.service import EvalDatasetKB

try:  # S-4 canonical platform logger (PB-1)
    from shared.utils.audit_logger import emit_trace_event
except ImportError:  # local test env without the platform
    from src.utils.audit import emit_trace_event


class CheckMatchNode(FunctionNode):
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("error_code") or state.get("retrieved_passages") is None:
            emit_trace_event("checks_matched", {"count": 0, "skipped": True}, state)
            return {}
        retrieved = json.loads(state["retrieved_passages"])
        checks = EvalDatasetKB.recommended_checks(retrieved)
        emit_trace_event("checks_matched", {"count": len(checks)}, state)
        return {"recommended_checks": json.dumps(checks, ensure_ascii=False), "status": AgentStatus.SUCCESS.value}
