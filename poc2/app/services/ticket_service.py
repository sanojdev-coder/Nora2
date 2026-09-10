import json
import logging

from app.mcp.servicenow_mcp_server import ServiceNowMCPServer
from app.mcp.tool_schema import ServiceNowCreateIssueInput, ServiceNowIssueResult
from app.models.coverage import CoverageAssessmentReport
from app.models.rca import RCAAnalysisResult


logger = logging.getLogger(__name__)


class TicketService:
    def __init__(self):
        self.server = ServiceNowMCPServer()

    def should_create_ticket(self, report: CoverageAssessmentReport, rca_result: RCAAnalysisResult) -> bool:
        logger.info(
            "TicketService should_create_ticket request report_id=%s outage_detected=%s coverage_status=%s service_availability=%s confidence=%.2f",
            report.report_id,
            report.outage_detected,
            report.coverage_status,
            report.service_availability,
            rca_result.confidence,
        )
        decision = (
            report.outage_detected
            or report.coverage_status.lower() == "degraded"
            or report.service_availability.lower() != "full"
        )
        logger.info("TicketService should_create_ticket response=%s", decision)
        return decision

    def create_ticket(
        self,
        report: CoverageAssessmentReport,
        rca_result: RCAAnalysisResult,
    ) -> ServiceNowIssueResult:
        logger.info("TicketService create_ticket request report=%s rca=%s", report.model_dump(), rca_result.model_dump())
        description_payload = {
            "report": report.model_dump(),
            "rca": rca_result.model_dump(),
        }
        request = ServiceNowCreateIssueInput(
            report_id=report.report_id,
            subscriber_id=report.subscriber_id,
            serving_market=report.serving_market,
            short_description=f"NORA Coverage Alert {report.report_id} for {report.subscriber_id}",
            description=json.dumps(description_payload, ensure_ascii=True),
            impact=2,
            urgency=2,
            category="network",
            subcategory="performance",
        )
        response = self.server.create_issue(request)
        logger.info("TicketService create_ticket response=%s", response.model_dump())
        return response
