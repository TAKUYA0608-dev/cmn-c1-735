# CMN-C1-735 — Unit tests: composite MainNode (Cat 1 FunctionNode-in-main)

import inspect
import json

from framework.schemas.agent_status import AgentStatus

from src.nodes.main_node import MainNode


class TestMainNode:
    """Unit tests for the composite main node."""

    def setup_method(self):
        self.node = MainNode()

    def test_trust_level(self):
        assert self.node.required_trust_level.name == "VERIFIED_EXTERNAL"

    def test_composes_five_substeps(self):
        assert len(self.node._seq) == 5

    def test_grounded_path(self):
        # TC: contamination-detection question retrieves grounded, cited guidance.
        state = {
            "validated_query": "how do I detect n-gram overlap contamination between train and test",
            "classified_topics": None, "node_history": [], "error_log": [],
        }
        out = self.node.execute(state)
        assert out["status"] == AgentStatus.SUCCESS.value
        assert out["retrieval_hit_count"] > 0
        assert json.loads(out["citations"])
        assert "[" in out["assembled_answer"]  # inline citation markers

    def test_degraded_skips(self):
        # TC: error_code short-circuits the composite (no grounded body).
        out = self.node.execute({"error_code": "INJECTION_REJECTED"})
        assert out == {}

    def test_zero_hit_out_of_scope(self):
        out = self.node.execute({"validated_query": "totally-unrelated-zzz-topic-not-in-kb"})
        assert out["retrieval_hit_count"] == 0
        assert out.get("error_code") is None
        assert "outside the current knowledge base" in out["assembled_answer"]
        assert json.loads(out["citations"]) == []

    def test_execute_signature_config_free(self):
        # config-free execute(): execute(self, state) — no config parameter.
        params = list(inspect.signature(MainNode.execute).parameters.keys())
        assert params == ["self", "state"]
