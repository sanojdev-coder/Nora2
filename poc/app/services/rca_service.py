import json
import logging

from app.mcp.azure_openai_client import AzureOpenAIClient
from app.mcp.snowflake_mcp_server import SnowflakeMCPServer
from app.mcp.tool_schema import CoverageAssessmentInput
from app.models.coverage import CoverageAssessmentReport
from app.models.rca import RCAAnalysisResult
from app.services.ticket_history_repository import TicketHistoryRepository


logger = logging.getLogger(__name__)


def _summarize_execution_value(value: dict | list | str | None, *, max_chars: int = 220) -> str:
    text = json.dumps(value, ensure_ascii=True, default=str)
    if len(text) > max_chars:
        text = text[: max_chars - 3] + "..."
    return text


class RCAService:
    def __init__(self):
        self.ai_client = AzureOpenAIClient()
        self.ticket_history = TicketHistoryRepository()
        self.snowflake_client = SnowflakeMCPServer()

    def _build_operational_context(self, subscriber_id: str) -> dict:
        data = self.snowflake_client.get_subscriber_operational_data(subscriber_id)
        return {
            "subscriber_id": data.get("subscriber_id", subscriber_id),
            "provision_status": data.get("provision_status", "UNKNOWN"),
            "package": data.get("package", "UNKNOWN"),
        }

    def _build_troubleshooting_guidance(self, operational_context: dict) -> list[str]:
        package_status = str(operational_context.get("package", "")).upper()
        guidance = [
            "Validate subscriber provisioning status and service package configuration.",
            "Confirm the subscriber is active and authorized for the current service bundle.",
        ]
        if package_status == "INVALID":
            guidance.append(
                "Subscriber package is INVALID; verify package entitlement and re-provision the service before escalating as a network outage."
            )
        return guidance

    def analyze(self, report: CoverageAssessmentReport) -> RCAAnalysisResult:
        logger.info("RCA analyze request=%s", report.model_dump())
        if not report.serving_market:
            raise ValueError("serving_market is required")

        prior_tickets = self.ticket_history.get_previous_tickets(report.subscriber_id, limit=10)
        logger.info(
            "RCA prior ticket lookup subscriber=%s prior_tickets=%s",
            report.subscriber_id,
            prior_tickets,
        )

        operational_context = self._build_operational_context(report.subscriber_id)
        troubleshooting_guidance = self._build_troubleshooting_guidance(operational_context)
        logger.info(
            "RCA operational context subscriber=%s context=%s troubleshooting=%s",
            report.subscriber_id,
            operational_context,
            troubleshooting_guidance,
        )

        tool_input = CoverageAssessmentInput(
            report_id=report.report_id,
            subscriber_id=report.subscriber_id,
            coverage_status=report.coverage_status,
            service_availability=report.service_availability,
            outage_detected=report.outage_detected,
            serving_market=report.serving_market,
            roaming_state=report.roaming_state,
            registration_state=report.registration_state,
            observations=report.observations,
            notes=report.notes,
            subscriber_operational_context=operational_context,
        )
        logger.info("RCA analyze tool_input=%s", tool_input.model_dump())

        llm_result = self.ai_client.analyze_coverage_report(tool_input, previous_tickets=prior_tickets)
        logger.info("RCA analyze llm_result=%s", llm_result.model_dump())

        openai_state = "live call"
        if self.ai_client.last_status == "stub":
            openai_state = "stub fallback"
            if self.ai_client.last_error:
                openai_state = f"stub fallback ({self.ai_client.last_error[:120]})"

        openai_request_summary = {
            "report_id": tool_input.report_id,
            "subscriber_id": tool_input.subscriber_id,
            "serving_market": tool_input.serving_market,
            "coverage_status": tool_input.coverage_status,
            "service_availability": tool_input.service_availability,
            "outage_detected": tool_input.outage_detected,
            "subscriber_operational_context": operational_context,
            "previous_tickets": prior_tickets,
        }
        openai_response_summary = {
            "report_id": llm_result.report_id,
            "root_cause_summary": llm_result.root_cause_summary,
            "confidence": llm_result.confidence,
            "recommended_actions": llm_result.recommended_actions,
            "mode": llm_result.mode,
        }

        execution_path = [
            "langgraph: invoked",
            f"openai: state={openai_state}",
            f"openai: request={_summarize_execution_value(openai_request_summary)}",
            f"openai: response={_summarize_execution_value(openai_response_summary)}",
        ]

        if troubleshooting_guidance:
            llm_result.recommended_actions = llm_result.recommended_actions + troubleshooting_guidance

        response = RCAAnalysisResult(
            report_id=llm_result.report_id,
            root_cause_summary=llm_result.root_cause_summary,
            confidence=llm_result.confidence,
            mode=llm_result.mode,
            recommended_actions=llm_result.recommended_actions,
            execution_path=execution_path,
        )
        logger.info("RCA analyze response=%s", response.model_dump())
        return response
