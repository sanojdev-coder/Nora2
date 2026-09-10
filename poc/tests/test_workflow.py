import json
import pytest
import logging
import sys
from pathlib import Path
from pydantic import ValidationError

import app.orchestrator.workflow as workflow_module
from app.mcp.azure_openai_client import AzureOpenAIClient
from app.models.coverage import CoverageAssessmentReport
from app.orchestrator.workflow import CoverageDiagnosticsWorkflow
from app.models.coverage import CoverageAssessmentReport
from app.models.rca import RCAAnalysisResult


REAL_LANGGRAPH_SKIP_REASON = (
    "langgraph is not installed in this environment "
    f"(python={sys.executable})"
)


def test_coverage_report_validates_allowed_subscriber_range():
    valid = CoverageAssessmentReport(
        report_id="CAR-201",
        subscriber_id="sub-202",
        coverage_status="degraded",
        service_availability="partial",
        outage_detected=True,
        serving_market="ATL-01",
        roaming_state="home",
        registration_state="registered",
        observations=["coverage degradation"],
    )
    assert valid.subscriber_id == "sub-202"

    with pytest.raises(ValueError, match="sub-201.*sub-210"):
        CoverageAssessmentReport(
            report_id="CAR-999",
            subscriber_id="sub-999",
            coverage_status="degraded",
            service_availability="partial",
            outage_detected=True,
            serving_market="ATL-01",
            roaming_state="home",
            registration_state="registered",
            observations=["coverage degradation"],
        )


def test_workflow_runs_in_static_sequence():
    workflow = CoverageDiagnosticsWorkflow()

    report = CoverageAssessmentReport(
        report_id="CAR-001",
        subscriber_id="sub-202",
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
        subscriber_id="sub-210",
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


def test_workflow_reports_execution_path():
    workflow = CoverageDiagnosticsWorkflow()
    report = CoverageAssessmentReport(
        report_id="CAR-303",
        subscriber_id="sub-203",
        coverage_status="degraded",
        service_availability="partial",
        outage_detected=True,
        serving_market="ATL-01",
        roaming_state="home",
        registration_state="registered",
        observations=["coverage degradation"],
    )

    result = workflow.run(report)

    assert hasattr(result, "execution_path")
    assert any("langgraph" in step.lower() for step in result.execution_path)
    assert any("openai" in step.lower() for step in result.execution_path)


def test_azure_openai_client_loads_settings_from_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AZURE_OPENAI_ENDPOINT=https://example.services.ai.azure.com\n"
        "AZURE_OPENAI_API_KEY=test-key\n"
        "AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)

    client = AzureOpenAIClient()

    assert client.endpoint == "https://example.services.ai.azure.com"
    assert client.api_key == "test-key"
    assert client.deployment == "gpt-4.1-mini"


def test_azure_openai_client_logs_requests_and_responses(tmp_path, monkeypatch):
    audit_path = tmp_path / "audit" / "openai_audit.jsonl"
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.services.ai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    monkeypatch.setenv("OPENAI_AUDIT_LOG_PATH", str(audit_path))

    client = AzureOpenAIClient()

    class FakeMessage:
        content = (
            '{"root_cause_summary":"Detected degradation","confidence":0.91,'
            '"hypotheses":[{"type":"outage","description":"Problem detected","confidence":0.89}],'
            '"recommended_actions":["Check outage feed"]}'
        )

    class FakeChoice:
        message = FakeMessage()

    class FakeCompletions:
        def create(self, **kwargs):
            return type("CompletionResult", (), {"choices": [FakeChoice()]})()

    class FakeChat:
        completions = FakeCompletions()

    class FakeAzureClient:
        chat = FakeChat()

    client._azure_client = FakeAzureClient()

    report = CoverageAssessmentReport(
        report_id="CAR-900",
        subscriber_id="sub-205",
        coverage_status="degraded",
        service_availability="partial",
        outage_detected=True,
        serving_market="ATL-99",
        roaming_state="home",
        registration_state="registered",
        observations=["degraded coverage"],
    )

    result = client.analyze_coverage_report(report)

    assert result.mode == "live"
    assert audit_path.exists()
    with audit_path.open("r", encoding="utf-8") as handle:
        record = json.loads(handle.readline().strip())
    assert record["report_id"] == "CAR-900"
    assert record["status"] == "success"
    assert record["request"]["report_id"] == "CAR-900"
    assert "root_cause_summary" in record["response"]["parsed_response"]


def test_azure_openai_client_includes_previous_tickets_in_prompt(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.services.ai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini")
    monkeypatch.delenv("OPENAI_AUDIT_LOG_PATH", raising=False)

    client = AzureOpenAIClient()

    class FakeMessage:
        content = (
            '{"root_cause_summary":"Detected degradation","confidence":0.91,'
            '"hypotheses":[{"type":"outage","description":"Problem detected","confidence":0.89}],'
            '"recommended_actions":["Check outage feed"]}'
        )

    class FakeChoice:
        message = FakeMessage()

    class FakeCompletions:
        def __init__(self):
            self.last_kwargs = None

        def create(self, **kwargs):
            self.last_kwargs = kwargs
            return type("CompletionResult", (), {"choices": [FakeChoice()]})()

    fake_completions = FakeCompletions()

    class FakeChat:
        completions = fake_completions

    class FakeAzureClient:
        chat = FakeChat()

    client._azure_client = FakeAzureClient()
    client.ticket_history = type(
        "FakeTicketHistory",
        (),
        {"get_previous_tickets": lambda self, subscriber_id, limit=10: ["INC0010020", "INC0010022"]},
    )()

    report = CoverageAssessmentReport(
        report_id="CAR-700",
        subscriber_id="sub-204",
        coverage_status="degraded",
        service_availability="partial",
        outage_detected=True,
        serving_market="ATL-01",
        roaming_state="home",
        registration_state="registered",
        observations=["coverage degradation", "regional outage"],
    )

    client.analyze_coverage_report(report)

    prompt_text = fake_completions.last_kwargs["messages"][1]["content"]
    assert '"previous_tickets": ["INC0010020", "INC0010022"]' in prompt_text


def test_rca_service_adds_subscriber_operational_context_and_invalid_package_guidance(monkeypatch):
    service = workflow_module.RCAService()

    class FakeAIClient:
        def __init__(self):
            self.last_status = "live"
            self.last_error = None
            self.last_request = None
            self.last_previous_tickets = None

        def analyze_coverage_report(self, report, previous_tickets=None):
            self.last_request = report.model_dump()
            self.last_previous_tickets = previous_tickets
            return type(
                "Result",
                (),
                {
                    "report_id": report.report_id,
                    "root_cause_summary": "Detected issue",
                    "confidence": 0.9,
                    "mode": "live",
                    "recommended_actions": ["Check outage"],
                    "model_dump": lambda self: {
                        "report_id": report.report_id,
                        "root_cause_summary": "Detected issue",
                        "confidence": 0.9,
                        "mode": "live",
                        "recommended_actions": ["Check outage"],
                    },
                },
            )()

    fake_ai = FakeAIClient()
    service.ai_client = fake_ai
    service.ticket_history = type(
        "FakeTicketHistory",
        (),
        {"get_previous_tickets": lambda self, subscriber_id, limit=10: ["INC0010031"]},
    )()
    service.snowflake_client = type(
        "FakeSnowflakeClient",
        (),
        {"get_subscriber_operational_data": lambda self, subscriber_id: {"subscriber_id": subscriber_id, "provision_status": "ON", "package": "INVALID"}},
    )()

    report = CoverageAssessmentReport(
        report_id="CAR-777",
        subscriber_id="sub-207",
        coverage_status="degraded",
        service_availability="partial",
        outage_detected=True,
        serving_market="ATL-01",
        roaming_state="home",
        registration_state="registered",
        observations=["coverage degradation"],
    )

    result = service.analyze(report)

    assert fake_ai.last_request["subscriber_id"] == "sub-207"
    assert fake_ai.last_request["subscriber_operational_context"]["package"] == "INVALID"
    assert any("INVALID" in action for action in result.recommended_actions)


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
        subscriber_id="sub-201",
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
