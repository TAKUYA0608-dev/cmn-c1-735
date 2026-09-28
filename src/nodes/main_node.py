"""CMN-C1-735 — main composite node (Cat 1).

Composes the 5 lineage/contamination capability steps in fixed order:
    TopicClassify → KBRetrieve → CheckMatch → RemediationAssemble → AnswerAssemble

Sub-nodes are instantiated in __init__ and called via sub.execute(state) directly
(single S-2/S-3/S-4 boundary; a sibling template composite pattern). Each self-skips on
error_code, so a degraded (rejected) input flows straight through to post_process.
Deterministic — no LLM.
"""

from __future__ import annotations

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.nodes.answer_assemble_node import AnswerAssembleNode
from src.nodes.check_match_node import CheckMatchNode
from src.nodes.kb_retrieve_node import KBRetrieveNode
from src.nodes.remediation_assemble_node import RemediationAssembleNode
from src.nodes.topic_classify_node import TopicClassifyNode

try:  # S-4 canonical platform logger (PB-1)
    from shared.utils.audit_logger import emit_trace_event
except ImportError:  # local test env without the platform
    from src.utils.audit import emit_trace_event


class MainNode(FunctionNode):
    """main slot — orchestrates the lineage/contamination steps → cited answer."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def __init__(self) -> None:
        super().__init__()
        self._seq: list[FunctionNode] = [
            TopicClassifyNode(),
            KBRetrieveNode(),
            CheckMatchNode(),
            RemediationAssembleNode(),
            AnswerAssembleNode(),
        ]

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("error_code"):
            emit_trace_event("lineage_answer_assembled", {"hit_count": 0, "grounded": False, "skipped": True}, state)
            return {}
        working = dict(state)
        deltas: dict[str, Any] = {}
        for node in self._seq:
            updates = node.execute(working) or {}
            working.update(updates)
            deltas.update(updates)

        emit_trace_event(
            "lineage_answer_assembled",
            {"hit_count": deltas.get("retrieval_hit_count", 0), "grounded": bool(deltas.get("retrieval_hit_count", 0))},
            state,
        )
        deltas["status"] = AgentStatus.SUCCESS.value
        return deltas
