import pytest
import logging
import sys
from pydantic import ValidationError

import app.orchestrator.workflow as workflow_module
from app.orchestrator.workflow import CoverageDiagnosticsWorkflow
from app.models.coverage import CoverageAssessmentReport
from app.models.rca import RCAAnalysisResult


REAL_LANGGRAPH_SKIP_REASON = (
    "langgraph is not installed in this environment "
    f"(python={sys.executable})"
)


def test_workflow_runs_in_static_sequence():
    workflow = CoverageDiagnosticsWorkflow()

    report = CoverageAssessmentReport(
        report_id="CAR-001",
        subscriber_id="sub-123",
        coverage_status="degraded",
        service_availability="partial",
        outage_detected=True,
        serving_market="ATL-01",
        roaming_state="home",
        registration_state="registered",
        observations=["coverage degradation", "regional outage"]
    )

    rca_result = workflow.run(report)

    assert isinstance(rca_result, RCAAnalysisResult)
    assert rca_result.report_id == "CAR-001"
    assert rca_result.root_cause_summary
    assert rca_result.recommended_actions


def test_workflow_rejects_missing_required_fields():
    with pytest.raises(ValidationError, match="at least 1 character"):
        CoverageAssessmentReport(
            report_id="CAR-002",
            subscriber_id="sub-456",
            coverage_status="degraded",
            service_availability="partial",
            outage_detected=False,
            serving_market="",
            roaming_state="home",
            registration_state="registered",
            observations=[]
        )

    workflow = CoverageDiagnosticsWorkflow()
    valid_report = CoverageAssessmentReport(
        report_id="CAR-003",
        subscriber_id="sub-789",
        coverage_status="normal",
        service_availability="full",
        outage_detected=False,
        serving_market="ATL-02",
        roaming_state="home",
        registration_state="registered",
        observations=[]
    )
    assert workflow.validate_report(valid_report) is True


def test_workflow_builds_langgraph_graph():
    workflow = CoverageDiagnosticsWorkflow()

    assert workflow.graph is not None
    assert hasattr(workflow, "run_langgraph")


def test_workflow_runs_with_langgraph_mode_on(monkeypatch, caplog):
    class FakeCompiledGraph:
        def __init__(self, nodes):
            self.nodes = nodes

        def invoke(self, state):
            next_state = dict(state)
            next_state.update(self.nodes["fetch_coverage"](next_state))
            next_state.update(self.nodes["analyze_rca"](next_state))
            next_state.update(self.nodes["create_ticket"](next_state))
            next_state.update(self.nodes["compose_response"](next_state))
            return next_state

    class FakeStateGraph:
        def __init__(self, _state_type):
            self.nodes = {}

        def add_node(self, name, fn):
            self.nodes[name] = fn

        def add_edge(self, _src, _dst):
            return None

        def compile(self):
            return FakeCompiledGraph(self.nodes)

    monkeypatch.setattr(workflow_module, "StateGraph", FakeStateGraph)
    monkeypatch.setattr(workflow_module, "START", "START")
    monkeypatch.setattr(workflow_module, "END", "END")

    caplog.set_level(logging.INFO)
    workflow = CoverageDiagnosticsWorkflow()
    report = CoverageAssessmentReport(
        report_id="CAR-101",
        subscriber_id="sub-123",
        coverage_status="degraded",
        service_availability="partial",
        outage_detected=True,
        serving_market="ATL-01",
        roaming_state="home",
        registration_state="registered",
        observations=["coverage degradation", "regional outage"],
    )

    result = workflow.run_langgraph(report)

    assert isinstance(result, RCAAnalysisResult)
    assert result.report_id == "CAR-101"
    assert "Workflow graph mode=langgraph" in caplog.text
    assert "Workflow node create_ticket response=" in caplog.text


@pytest.mark.skipif(
    workflow_module.StateGraph is None,
    reason=REAL_LANGGRAPH_SKIP_REASON,
)
def test_workflow_runs_with_real_langgraph_mode_on(caplog):
    caplog.set_level(logging.INFO)
    workflow = CoverageDiagnosticsWorkflow()
    report = CoverageAssessmentReport(
        report_id="CAR-202",
        subscriber_id="sub-202",
        coverage_status="degraded",
        service_availability="partial",
        outage_detected=True,
        serving_market="ATL-01",
        roaming_state="home",
        registration_state="registered",
        observations=["coverage degradation", "regional outage"],
    )

    result = workflow.run_langgraph(report)

    assert isinstance(result, RCAAnalysisResult)
    assert result.report_id == "CAR-202"
    assert workflow.graph.__class__.__module__.startswith("langgraph")
    assert "Workflow graph mode=langgraph" in caplog.text
