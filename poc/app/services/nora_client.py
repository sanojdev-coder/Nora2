import logging
import random

from app.models.coverage import CoverageAssessmentReport


logger = logging.getLogger(__name__)


class NORAClient:
    def __init__(self):
        self.base_url = "https://example-nora-api.local"

    @staticmethod
    def _random_subscriber_id() -> str:
        return f"sub-{random.randint(201, 210)}"

    def get_coverage_assessment(self, request: dict) -> CoverageAssessmentReport:
        logger.info("NORA get_coverage_assessment request=%s", request)
        requested_subscriber = request.get("subscriber_id")
        if not requested_subscriber:
            requested_subscriber = self._random_subscriber_id()

        response = CoverageAssessmentReport(
            report_id=request.get("report_id", "CAR-001"),
            subscriber_id=requested_subscriber,
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
