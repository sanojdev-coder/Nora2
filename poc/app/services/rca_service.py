import logging

from app.mcp.azure_openai_client import AzureOpenAIClient
from app.mcp.tool_schema import CoverageAssessmentInput
from app.models.coverage import CoverageAssessmentReport
from app.models.rca import RCAAnalysisResult


logger = logging.getLogger(__name__)


class RCAService:
    def __init__(self):
        self.ai_client = AzureOpenAIClient()

    def analyze(self, report: CoverageAssessmentReport) -> RCAAnalysisResult:
        logger.info("RCA analyze request=%s", report.model_dump())
        if not report.serving_market:
            raise ValueError("serving_market is required")

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
        )
        logger.info("RCA analyze tool_input=%s", tool_input.model_dump())

        llm_result = self.ai_client.analyze_coverage_report(tool_input)
        logger.info("RCA analyze llm_result=%s", llm_result.model_dump())

        response = RCAAnalysisResult(
            report_id=llm_result.report_id,
            root_cause_summary=llm_result.root_cause_summary,
            confidence=llm_result.confidence,
            recommended_actions=llm_result.recommended_actions,
        )
        logger.info("RCA analyze response=%s", response.model_dump())
        return response
