import logging

from app.models.coverage import CoverageAssessmentReport


logger = logging.getLogger(__name__)


class NORAClient:
    def __init__(self):
        self.base_url = "https://example-nora-api.local"

    def get_coverage_assessment(self, request: dict) -> CoverageAssessmentReport:
        logger.info("NORA get_coverage_assessment request=%s", request)
        response = CoverageAssessmentReport(
            report_id=request.get("report_id", "CAR-001"),
            subscriber_id=request.get("subscriber_id", "sub-123"),
            coverage_status="degraded",
            service_availability="partial",
            outage_detected=True,
            serving_market="ATL-01",
            roaming_state="home",
            registration_state="registered",
            observations=["coverage degradation", "regional outage"],
            notes="Example local NORA coverage assessment response.",
        )
        logger.info("NORA get_coverage_assessment response=%s", response.model_dump())
        return response
