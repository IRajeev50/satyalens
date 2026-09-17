"""Run gold examples through the live verification pipeline (Phase 8).

Each example goes through the same ``pipeline.verify`` path the API uses:
sanitize -> injection scan -> claim gate -> retrieval -> rubric -> stored
assessment. Runs execute against a throwaway SQLite database so eval traffic
never touches dev or production data, and every example still gets the real
claim gate, the real injection scan and the real rubric.

Nothing is simulated. When ``GOOGLE_FACTCHECK_API_KEY`` is not configured,
retrieval returns zero evidence exactly as the live system does, and the
report labels the run as no-external-evidence rather than pretending the
verdicts say anything about quality.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import models  # noqa: F401  (register all tables on Base.metadata)
from backend.app.config import settings
from backend.app.database import Base
from backend.app.models import CaseStatus
from backend.app.services import pipeline
from backend.app.services.claim_gate import GATE_PROCEED

from ..validate_seed import load_schema, validate_seed
from .metrics import Prediction

EVAL_DB_PREFIX = "satyalens-eval-"


def retrieval_mode() -> str:
    """Describe, honestly, how retrieval behaves in this run."""
    if settings.google_factcheck_api_key:
        return "live: GOOGLE_FACTCHECK_API_KEY configured; real Google Fact Check API calls are made"
    return ("no_external_evidence: GOOGLE_FACTCHECK_API_KEY is not configured; retrieval returns zero "
            "items and every checkable claim is assessed on no evidence, exactly as the live system does")


def run_seed(seed: list[dict], db_url: str | None = None) -> list[Prediction]:
    """Validate a gold set against the schema, then run every example."""
    validate_seed(seed, load_schema())
    tmp_path = None
    if db_url is None:
        fd, tmp_path = tempfile.mkstemp(prefix=EVAL_DB_PREFIX, suffix=".db")
        os.close(fd)
        db_url = f"sqlite:///{tmp_path}"
    try:
        engine = create_engine(db_url, connect_args={"check_same_thread": False}
                               if db_url.startswith("sqlite") else {}, future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        return asyncio.run(_run_all(seed, session_factory))
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


async def _run_all(seed: list[dict], session_factory) -> list[Prediction]:
    predictions = []
    for example in seed:
        predictions.append(await _run_one(example, session_factory))
    return predictions


async def _run_one(example: dict, session_factory) -> Prediction:
    started = time.perf_counter()
    with session_factory() as db:
        case, warnings = await pipeline.verify(db, example["input"]["text"], None)
        claims = list(case.claims)
        stored_ids = tuple(sorted(item.id for claim in claims for item in claim.evidence_items))
        cited_ids = tuple(case.assessment.evidence_ids) if case.assessment else ()
        verdict = case.assessment.verdict if case.assessment else "unverifiable"
        confidence = case.assessment.confidence if case.assessment else "Low"
        flagged = any(f.get("type") == "prompt_injection_suspected" for f in (case.security_flags or []))
        sensitivity_flagged = any(f.get("type") == "sensitive_claim" for f in (case.security_flags or []))
        checkable = [c for c in claims if c.gate_status == GATE_PROCEED]
        # Retrieval runs only when the injection scan is clean and at least one
        # claim passed the gate; this mirrors pipeline._run_case exactly.
        retrieval_attempted = (not flagged) and (not sensitivity_flagged) and bool(checkable)
        status_value = case.status.value if isinstance(case.status, CaseStatus) else str(case.status)
        # pending_review remains universal, but sensitive routing is a distinct gate signal.
        routed_to_human = flagged or sensitivity_flagged or verdict == "unverifiable"
        predicted_types = tuple(sorted({c.claim_type for c in claims}))
    latency_ms = (time.perf_counter() - started) * 1000.0
    return Prediction(
        id=example["id"],
        bucket=example["bucket"],
        language=example["input"]["language"],
        synthetic=example["synthetic"],
        expected_claim_types=tuple(sorted(example["expected"]["claim_types"])),
        expected_veracity=example["expected"]["veracity"],
        expected_route_to_human=example["expected"]["route_to_human"],
        predicted_claim_types=predicted_types,
        verdict=verdict,
        confidence=confidence,
        routed_to_human=routed_to_human,
        security_flagged=flagged,
        retrieval_attempted=retrieval_attempted,
        evidence_count=len(stored_ids),
        cited_evidence_ids=cited_ids,
        stored_evidence_ids=stored_ids,
        latency_ms=latency_ms,
        sensitivity_flagged=sensitivity_flagged,
        warnings=tuple(warnings),
    )
