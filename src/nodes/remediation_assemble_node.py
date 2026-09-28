"""RemediationAssembleNode — composite sub-step 4: KB-grounded remediation steps.

Deterministic: assembles the recommended remediation / mitigation steps from the
retrieved KB records (each step carries its source doc_ref). No free LLM
generation — steps come from KB templates only, so guidance stays auditable.
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


class RemediationAssembleNode(FunctionNode):
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("error_code") or state.get("retrieved_passages") is None:
            emit_trace_event("remediation_assembled", {"count": 0, "skipped": True}, state)
            return {}
        retrieved = json.loads(state["retrieved_passages"])
        steps = EvalDatasetKB.remediation_steps(retrieved)
        emit_trace_event("remediation_assembled", {"count": len(steps)}, state)
        return {"remediation_steps": json.dumps(steps, ensure_ascii=False), "status": AgentStatus.SUCCESS.value}
