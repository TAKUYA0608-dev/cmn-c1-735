"""AnswerAssembleNode — composite sub-step 5: assemble the cited answer.

Assembles the grounded, cited ``assembled_answer`` from the retrieved passages,
recommended checks, and remediation steps. A 0-hit retrieval yields an in-scope
"out-of-scope / insufficient grounding" safe answer (no hallucinated advice).
Deterministic — no LLM.
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


class AnswerAssembleNode(FunctionNode):
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("error_code") or state.get("retrieved_passages") is None:
            emit_trace_event("answer_assembled", {"grounded": False, "skipped": True}, state)
            return {}
        retrieved = json.loads(state["retrieved_passages"])
        checks = json.loads(state.get("recommended_checks") or "[]")
        remediation = json.loads(state.get("remediation_steps") or "[]")

        if not retrieved:
            answer = (
                "This lineage/contamination question is outside the current knowledge base "
                "(contamination detection / dedup / benchmark leakage / dataset lineage & "
                "provenance / canary handling / documentation standards). No grounded guidance "
                "is available for this request."
            )
            citations: list[dict[str, Any]] = []
        else:
            topics = sorted({r["topic"] for r in retrieved})
            lines = [f"Guidance for: {', '.join(topics)}"]
            for r in retrieved:
                lines.append(f"- {r['text']} [{r['doc_ref']}]")
            for c in checks:
                lines.append(f"- Recommended check ({c['method_type']}): {c['check']} [{c['doc_ref']}]")
            for s in remediation:
                lines.append(f"- Remediation: {s['step']} [{s['doc_ref']}]")
            answer = "\n".join(lines)
            citations = [{"marker": r["doc_ref"], "source": r["source"], "doc_ref": r["doc_ref"]} for r in retrieved]

        emit_trace_event("answer_assembled", {"grounded": bool(retrieved), "citation_count": len(citations)}, state)
        return {
            "assembled_answer": EvalDatasetKB.redact(answer),
            "citations": json.dumps(citations, ensure_ascii=False),
            "status": AgentStatus.SUCCESS.value,
        }
