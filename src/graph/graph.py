"""AgentCore Platform v1.0"""

from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Template Category (Cat) — choose ONE based on your Cat judgment:
#
# Cat 1 — Single technical capability (use-case-agnostic)
#   Purpose : Delivers one reusable, domain-independent capability.
#             The same template can be dropped into any project unchanged.
#   Examples: TextSummarizer, EmbeddingGenerator, LanguageDetector,
#             SentimentAnalyzer, KeywordExtractor
#   Parent  : AgentBaseGraph
#   Pipeline: START → initialize → pre_process → main → {route} → post_process → finalize → END
#                                             ↓ (RETRY, max 3)
#                                          pre_process
#   See src/examples/graph_cat1_sample.py for a full example.
#
# Cat 2 — Multi-step domain workflow (job-to-be-done)
#   Purpose : Orchestrates multiple steps to accomplish a specific business
#             outcome. The template name describes the outcome, not the
#             individual capabilities it uses.
#   Examples: InvoiceTriageAgent, ContractGapDetectionAgent,
#             ResumeScreeningAgent, SupportTicketResolutionAgent
#   Parent  : AgentBaseGraph (outer graph) + GraphNode in the `main` slot
#             wrapping an inner BaseGraph/AgentBaseGraph (domain workflow)
#   Pipeline: Same fixed 5-node backbone as Cat 1; domain complexity is
#             encapsulated inside DomainWorkflowGraphNode.get_subgraph().
#   Layout  : src/graph/graph.py                 ← outer graph (this file)
#             src/graph/domain_workflow_graph.py ← inner graph
#   See src/examples/graph_cat2_sample.py and src/examples/domain_workflow_graph_sample.py for examples.
#
# Cat 3 — Autonomous think→act→observe loop (self-directed)
#   Purpose : Runs an LLM-driven loop that decides its own next action,
#             executes tools, observes results, and terminates when the task
#             is complete or a budget/iteration ceiling is hit.
#   Examples: ResearchAgent, AutonomousCodeReviewAgent,
#             DataExplorationAgent, MultiStepPlannerAgent
#   Parent  : AutonomousBaseGraph
#   Pipeline: START → initialize → think ⇄ act → finalize → END
#   Config  : budget_usd and llm are required in config.yaml.
#   See src/examples/graph_cat3_sample.py for a full example.
#
# ── How to choose ─────────────────────────────────────────────────────────────
#
#   Ask: "Does this template solve a specific business problem end-to-end?"
#     No  → Cat 1 (generic capability)
#     Yes → "Does it need an autonomous reasoning loop to decide its steps?"
#       No  → Cat 2 (fixed multi-step workflow)
#       Yes → Cat 3 (LLM-driven loop)
#
# framework.* imports are unchanged; agent-local imports use the src. prefix.
# ─────────────────────────────────────────────────────────────────────────────

from framework.graph.agent_base_graph import AgentBaseGraph
from src.nodes.main_node import MainNode
from src.nodes.post_process_node import ResponseValidateNode
from src.nodes.pre_process_node import QueryNormalizeNode
from src.schemas.state import State


class Graph(AgentBaseGraph):
    """Fixed-pipeline graph (Cat 1 composite FunctionNode-in-main)."""

    @property
    def name(self) -> str:
        return "EvaluationDatasetLineageContaminationAgent"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        # super() injects "initialize" and "finalize" slots automatically.
        # They are shown here as sample code only — do NOT re-register them
        # unless you are providing a custom subclass.
        #
        # Sample (for reference — already injected by super()):
        #   self._nodes["initialize"] = InitializeNode()   # sets schema_version,
        #                                                    # session_id, trust_level
        #   self._nodes["finalize"]   = FinalizeNode()     # builds response_metadata,
        #                                                    # total_time_ms
        #
        # To customise: subclass InitializeNode / FinalizeNode and override
        # on_initialize() / on_finalize() respectively; then register here:
        #   self._nodes["initialize"] = CustomInitializeNode()
        #   self._nodes["finalize"]   = CustomFinalizeNode()
        super().register_nodes()  # injects InitializeNode + FinalizeNode

        # Domain pipeline slots (required — fill all three):
        self._nodes["pre_process"] = QueryNormalizeNode()
        self._nodes["main"] = MainNode()
        self._nodes["post_process"] = ResponseValidateNode()

    def get_output(self, state: dict[str, Any]) -> dict[str, Any]:
        """Framework default, plus the guarantee that a success is never empty.

        The Marketplace runner rejects a successful invocation whose output is
        missing — verified on a deployed Pod — and a degraded run
        (SUCCESS + error_code) produces no artefact for the framework default
        to surface. Report the degradation instead: this states what happened,
        it does not invent an answer.

        Only on SUCCESS. A request refused by the framework's S-2 gate (status
        ERROR) must keep publishing nothing — answering a hostile input with a
        notice would undo the refusal, and the runner treats a non-success
        invocation as a failure regardless, so there is nothing to rescue.
        """
        out: dict[str, Any] = super().get_output(state)
        if not out.get("output") and str(state.get("status", "")).lower().endswith("success"):
            code = state.get("error_code") or "NO_CONTENT"
            out["output"] = (
                "This request could not be completed "
                f"(error_code={code}). No content was produced; "
                "see error_code and error_log for the degradation cause."
            )
        return out


# AgentRegistry / config/agent.yaml `class:` resolution requires a module-level alias.
EvaluationDatasetLineageContaminationAgent = Graph
