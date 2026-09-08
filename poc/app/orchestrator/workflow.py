from typing import TypedDict
import logging

try:
    from langgraph.graph import END, START, StateGraph
except ModuleNotFoundError:  # pragma: no cover - exercised when LangGraph is absent
    END = START = StateGraph = None

from app.models.coverage import CoverageAssessmentReport
from app.models.rca import RCAAnalysisResult
from app.mcp.tool_schema import ServiceNowIssueResult
from app.services.nora_client import NORAClient
from app.services.rca_service import RCAService
from app.services.response_composer import ResponseComposer
from app.services.ticket_service import TicketService


logger = logging.getLogger(__name__)


class WorkflowState(TypedDict, total=False):
    report: CoverageAssessmentReport
    nora_response: CoverageAssessmentReport
    rca_result: RCAAnalysisResult
    ticket_result: ServiceNowIssueResult
    composed_response: dict


class _FallbackWorkflowGraph:
    def __init__(self, workflow: "CoverageDiagnosticsWorkflow"):
        self.workflow = workflow

    def invoke(self, state: WorkflowState) -> WorkflowState:
        logger.info("Fallback workflow invoke request=%s", state)
        next_state = dict(state)
        next_state.update(self.workflow._fetch_coverage(next_state))
        next_state.update(self.workflow._analyze_rca(next_state))
        next_state.update(self.workflow._create_ticket(next_state))
        next_state.update(self.workflow._compose_response(next_state))
        logger.info("Fallback workflow invoke response=%s", next_state)
        return next_state


class CoverageDiagnosticsWorkflow:
    def __init__(self):
        self.nora_client = NORAClient()
        self.rca_service = RCAService()
        self.ticket_service = TicketService()
        self.response_composer = ResponseComposer()
        self.graph = self._build_graph()

    def _build_graph(self):
        if StateGraph is None:
            logger.info("Workflow graph mode=fallback")
            return _FallbackWorkflowGraph(self)

        graph = StateGraph(WorkflowState)
        graph.add_node("fetch_coverage", self._fetch_coverage)
        graph.add_node("analyze_rca", self._analyze_rca)
        graph.add_node("create_ticket", self._create_ticket)
        graph.add_node("compose_response", self._compose_response)
        graph.add_edge(START, "fetch_coverage")
        graph.add_edge("fetch_coverage", "analyze_rca")
        graph.add_edge("analyze_rca", "create_ticket")
        graph.add_edge("create_ticket", "compose_response")
        graph.add_edge("compose_response", END)
        logger.info("Workflow graph mode=langgraph")
        return graph.compile()

    def _fetch_coverage(self, state: WorkflowState) -> WorkflowState:
        logger.info("Workflow node fetch_coverage request=%s", state)
        report = state["report"]
        response = {
            "nora_response": self.nora_client.get_coverage_assessment(
                {
                    "report_id": report.report_id,
                    "subscriber_id": report.subscriber_id,
                }
            )
        }
        logger.info("Workflow node fetch_coverage response=%s", response)
        return response

    def _analyze_rca(self, state: WorkflowState) -> WorkflowState:
        logger.info("Workflow node analyze_rca request=%s", state)
        response = {"rca_result": self.rca_service.analyze(state["nora_response"])}
        logger.info("Workflow node analyze_rca response=%s", response)
        return response

    def _create_ticket(self, state: WorkflowState) -> WorkflowState:
        logger.info("Workflow node create_ticket request=%s", state)
        report = state["nora_response"]
        rca_result = state["rca_result"]

        if not self.ticket_service.should_create_ticket(report, rca_result):
            response = {
                "ticket_result": ServiceNowIssueResult(
                    mode="decision",
                    action="create_issue",
                    success=False,
                    message="Ticket creation skipped by decision policy",
                )
            }
            logger.info("Workflow node create_ticket response=%s", response)
            return response

        response = {"ticket_result": self.ticket_service.create_ticket(report, rca_result)}
        logger.info("Workflow node create_ticket response=%s", response)
        return response

    def _compose_response(self, state: WorkflowState) -> WorkflowState:
        logger.info("Workflow node compose_response request=%s", state)
        response = {
            "composed_response": self.response_composer.compose(
                state["rca_result"],
                state.get("ticket_result"),
            )
        }
        logger.info("Workflow node compose_response response=%s", response)
        return response

    def validate_report(self, report: CoverageAssessmentReport) -> bool:
        logger.info("Workflow validate_report request=%s", report.model_dump())
        required_fields = [
            report.report_id,
            report.subscriber_id,
            report.coverage_status,
            report.service_availability,
            report.serving_market,
            report.roaming_state,
            report.registration_state,
        ]
        result = all(bool(field) for field in required_fields)
        logger.info("Workflow validate_report response=%s", result)
        return result

    def run(self, report: CoverageAssessmentReport) -> RCAAnalysisResult:
        logger.info("Workflow run request=%s", report.model_dump())
        return self.run_langgraph(report)

    def run_langgraph(self, report: CoverageAssessmentReport) -> RCAAnalysisResult:
        logger.info("Workflow run_langgraph request=%s", report.model_dump())
        if not self.validate_report(report):
            raise ValueError("CoverageAssessmentReport is missing required data")

        state = self.graph.invoke({"report": report})
        response = state["rca_result"]
        logger.info("Workflow run_langgraph response=%s", response.model_dump())
        return response
