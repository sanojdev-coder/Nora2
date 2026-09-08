import logging

from fastapi import APIRouter

from app.models.coverage import CoverageAssessmentReport
from app.orchestrator.workflow import CoverageDiagnosticsWorkflow


logger = logging.getLogger(__name__)

router = APIRouter()
workflow = CoverageDiagnosticsWorkflow()


@router.post("/coverage-diagnostics")
def coverage_diagnostics(report: CoverageAssessmentReport):
    logger.info("API coverage_diagnostics request=%s", report.model_dump())
    result = workflow.run(report)
    response = {
        "report_id": result.report_id,
        "root_cause_summary": result.root_cause_summary,
        "confidence": result.confidence,
        "recommended_actions": result.recommended_actions,
    }
    logger.info("API coverage_diagnostics response=%s", response)
    return response
