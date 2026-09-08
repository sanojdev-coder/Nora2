from typing import List

from pydantic import BaseModel, Field


class RCAAnalysisResult(BaseModel):
    report_id: str = Field(..., min_length=1)
    root_cause_summary: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    recommended_actions: List[str] = Field(default_factory=list)
