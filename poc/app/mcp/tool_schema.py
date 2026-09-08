from typing import List

from pydantic import BaseModel, Field


class CoverageAssessmentInput(BaseModel):
    report_id: str = Field(..., min_length=1)
    subscriber_id: str = Field(..., min_length=1)
    coverage_status: str = Field(..., min_length=1)
    service_availability: str = Field(..., min_length=1)
    outage_detected: bool
    serving_market: str = Field(..., min_length=1)
    roaming_state: str = Field(..., min_length=1)
    registration_state: str = Field(..., min_length=1)
    observations: List[str] = Field(default_factory=list)
    notes: str | None = None


class RCAHypothesis(BaseModel):
    type: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)


class RCAAnalysisToolResult(BaseModel):
    report_id: str = Field(..., min_length=1)
    root_cause_summary: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    hypotheses: List[RCAHypothesis] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)


class ServiceNowCreateIssueInput(BaseModel):
    report_id: str = Field(..., min_length=1)
    subscriber_id: str = Field(..., min_length=1)
    serving_market: str = Field(..., min_length=1)
    short_description: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    impact: int = Field(default=2, ge=1, le=3)
    urgency: int = Field(default=2, ge=1, le=3)
    category: str = Field(default="network", min_length=1)
    subcategory: str = Field(default="performance", min_length=1)


class ServiceNowGetIssueInput(BaseModel):
    sys_id: str | None = None
    number: str | None = None


class ServiceNowUpdateIssueInput(BaseModel):
    sys_id: str | None = None
    number: str | None = None
    state: str | None = None
    work_notes: str | None = None
    comments: str | None = None


class ServiceNowIssueResult(BaseModel):
    mode: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    success: bool
    message: str = Field(..., min_length=1)
    sys_id: str | None = None
    number: str | None = None
    state: str | None = None
    short_description: str | None = None
