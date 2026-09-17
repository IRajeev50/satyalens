from typing import Literal
from pydantic import BaseModel, Field, HttpUrl, model_validator

class VerifyRequest(BaseModel):
    text: str | None = Field(None, min_length=3, max_length=50_000)
    url: HttpUrl | None = None
    @model_validator(mode="after")
    def one_input(self):
        if bool(self.text) == bool(self.url):
            raise ValueError("Provide exactly one of text or url")
        return self

class EvidenceOut(BaseModel):
    id: str; source_title: str; source_url: str; publisher: str | None
    quote: str; relation: str; rating: str | None; retrieved_at: str
class ClaimOut(BaseModel):
    id: str; text: str; source_span: list[int]; claim_type: str; gate_status: str
    components: dict; evidence: list[EvidenceOut]
class AssessmentOut(BaseModel):
    verdict: Literal["supported","mostly supported","mixed","misleading","contradicted","unverifiable"]
    confidence: Literal["High","Moderate","Low"]
    rationale: str; reasoning_path: list[str]; rubric_version: str; evidence_ids: list[str]
class VerifyResponse(BaseModel):
    case_id: str; status: str; input_type: str; source_url: str | None; language: str
    claims: list[ClaimOut]; assessment: AssessmentOut; warnings: list[str]
    security_flags: list[dict]
class ReviewRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=100)
    decision: Literal["approve", "override", "needs_more_evidence"]
    reason: str = Field(min_length=2, max_length=2000)
    verdict: Literal["supported","mostly supported","mixed","misleading","contradicted","unverifiable"] | None = None
    @model_validator(mode="after")
    def override_needs_verdict(self):
        if self.decision == "override" and not self.verdict:
            raise ValueError("verdict is required for override")
        return self
