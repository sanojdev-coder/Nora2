from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class CoverageAssessmentReport(BaseModel):
    report_id: str = Field(..., min_length=1)
    subscriber_id: str = Field(..., min_length=1)
    coverage_status: str = Field(..., min_length=1)
    service_availability: str = Field(..., min_length=1)
    outage_detected: bool
    serving_market: str = Field(..., min_length=1)
    roaming_state: str = Field(..., min_length=1)
    registration_state: str = Field(..., min_length=1)
    observations: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

    @field_validator("observations")
    @classmethod
    def validate_observations(cls, value):
        return value or []
