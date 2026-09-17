import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base

def uid() -> str: return str(uuid.uuid4())
def now() -> datetime: return datetime.now(timezone.utc)

class CaseStatus(str, enum.Enum):
    draft = "draft"
    pending_review = "pending_review"
    reviewed = "reviewed"

class VerificationCase(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    input_type: Mapped[str] = mapped_column(String(20))
    original_input: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(20), default="unknown")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CaseStatus] = mapped_column(Enum(CaseStatus), default=CaseStatus.draft)
    security_flags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    claims: Mapped[list["Claim"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    assessment: Mapped["Assessment | None"] = relationship(back_populates="case", cascade="all, delete-orphan", uselist=False)
    reviews: Mapped[list["ReviewEvent"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    media_signals: Mapped[list["MediaSignal"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    intake_messages: Mapped[list["IntakeMessage"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    representations: Mapped[list["Representation"]] = relationship(back_populates="case", cascade="all, delete-orphan")

class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    text: Mapped[str] = mapped_column(Text)
    source_start: Mapped[int] = mapped_column()
    source_end: Mapped[int] = mapped_column()
    claim_type: Mapped[str] = mapped_column(String(20), default="checkable_fact")
    gate_status: Mapped[str] = mapped_column(String(20), default="proceed")
    components: Mapped[dict] = mapped_column(JSON, default=dict)
    case: Mapped[VerificationCase] = relationship(back_populates="claims")
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(back_populates="claim", cascade="all, delete-orphan")

class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"))
    source_url: Mapped[str] = mapped_column(Text)
    source_title: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(Text, nullable=True)
    quote: Mapped[str] = mapped_column(Text)
    relation: Mapped[str] = mapped_column(String(20), default="related")
    rating: Mapped[str | None] = mapped_column(String(100), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    claim: Mapped[Claim] = relationship(back_populates="evidence_items")

class Assessment(Base):
    __tablename__ = "assessments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), unique=True)
    verdict: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[str] = mapped_column(String(20))
    rationale: Mapped[str] = mapped_column(Text)
    reasoning_path: Mapped[list] = mapped_column(JSON, default=list)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    rubric_version: Mapped[str] = mapped_column(String(20))
    case: Mapped[VerificationCase] = relationship(back_populates="assessment")

class ReviewEvent(Base):
    __tablename__ = "review_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    actor: Mapped[str] = mapped_column(String(100))
    decision: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    case: Mapped[VerificationCase] = relationship(back_populates="reviews")


class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    kind: Mapped[str] = mapped_column(String(30))
    filename: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column()
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    case: Mapped[VerificationCase] = relationship(back_populates="artifacts")


class MediaSignal(Base):
    __tablename__ = "media_signals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    detector: Mapped[str] = mapped_column(String(100))
    detector_version: Mapped[str] = mapped_column(String(40))
    signal_type: Mapped[str] = mapped_column(String(50))
    finding: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(20))
    limitations: Mapped[str] = mapped_column(Text)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    case: Mapped[VerificationCase] = relationship(back_populates="media_signals")


class IntakeMessage(Base):
    __tablename__ = "intake_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    provider_message_id: Mapped[str] = mapped_column(String(150), unique=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(30))
    sender_hash: Mapped[str] = mapped_column(String(64))
    message_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="received")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    case: Mapped[VerificationCase | None] = relationship(back_populates="intake_messages")


class Representation(Base):
    __tablename__ = "representations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    kind: Mapped[str] = mapped_column(String(40))
    language: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    engine: Mapped[str] = mapped_column(String(60))
    confidence: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    case: Mapped[VerificationCase] = relationship(back_populates="representations")


class Monitor(Base):
    __tablename__ = "monitors"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    query: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(20), default="en")
    status: Mapped[str] = mapped_column(String(20), default="active")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_result_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
