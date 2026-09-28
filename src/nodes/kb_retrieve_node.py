"""KBRetrieveNode — composite sub-step 2: read-only deterministic KB retrieval.

A 0-hit retrieval is NOT an error — it routes to an in-scope out-of-scope safe
answer downstream (no hallucinated lineage/contamination advice).
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


class KBRetrieveNode(FunctionNode):
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("error_code") or state.get("classified_topics") is None:
            emit_trace_event("passages_retrieved", {"hit_count": 0, "skipped": True}, state)
            return {}
        topics = json.loads(state["classified_topics"])
        retrieved = EvalDatasetKB.retrieve(state.get("validated_query", ""), topics)
        emit_trace_event("passages_retrieved", {"hit_count": len(retrieved)}, state)
        return {
            "retrieved_passages": json.dumps(retrieved, ensure_ascii=False),
            "retrieval_hit_count": len(retrieved),
            "status": AgentStatus.SUCCESS.value,
        }
