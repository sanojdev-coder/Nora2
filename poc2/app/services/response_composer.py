import logging

from app.mcp.tool_schema import ServiceNowIssueResult
from app.models.rca import RCAAnalysisResult


logger = logging.getLogger(__name__)


class ResponseComposer:
    def compose(
        self,
        rca_result: RCAAnalysisResult,
        ticket_result: ServiceNowIssueResult | None = None,
    ) -> dict:
        logger.info("ResponseComposer compose request=%s", rca_result.model_dump())
        response = {
            "report_id": rca_result.report_id,
            "summary": rca_result.root_cause_summary,
            "confidence": rca_result.confidence,
            "recommended_actions": rca_result.recommended_actions,
            "status": "ok",
        }
        if ticket_result is not None:
            response["ticket"] = ticket_result.model_dump()
        logger.info("ResponseComposer compose response=%s", response)
        return response
