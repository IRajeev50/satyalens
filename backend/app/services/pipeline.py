from dataclasses import asdict
from sqlalchemy.orm import Session
from ..config import settings
from ..models import Assessment, CaseStatus, Claim, EvidenceItem, Representation, VerificationCase
from .claims import extract_claims
from .claim_gate import GATE_PROCEED, classify_claims
from .injection import sanitize_and_scan
from .retrieval import FactCheckRetriever
from .rubric import RUBRIC_VERSION, Finding, assess
from .url_fetch import fetch_article
from .language import analyze, normalize

INJECTION_WARNING = ("Potential prompt-injection pattern detected in ingested content; "
                     "external retrieval was skipped and the case was routed to human review.")


async def verify(db: Session, text: str | None, url: str | None) -> tuple[VerificationCase, list[str]]:
    if text is None:
        fetched = await fetch_article(str(url))
        return await _run_case(db, fetched, str(url), "url", str(url))
    return await _run_case(db, text, text, "text", None)


async def verify_normalized(db: Session, normalized: str, original_input: str, input_type: str,
                            source_url: str | None = None):
    return await _run_case(db, normalized, original_input, input_type, source_url)


async def _run_case(db: Session, raw_text: str, original_input: str, input_type: str,
                    source_url: str | None) -> tuple[VerificationCase, list[str]]:
    # Ingested content (pasted text, fetched article, OCR output, forwarded message)
    # is untrusted: sanitize first, then scan for prompt-injection patterns.
    cleaned, scan = sanitize_and_scan(raw_text)
    normalized = normalize(cleaned)
    lang = analyze(normalized)
    case = VerificationCase(input_type=input_type, original_input=original_input,
                            normalized_text=normalized, source_url=source_url, language=lang.label)
    case.representations.append(Representation(kind="normalized_original", language=lang.label,
                                               text=normalized, engine="unicode-nfc", confidence="High"))
    db.add(case); db.flush()

    # Phase 7 gate: type every claim before any verification. Only checkable
    # facts proceed; the rest are typed, first-class outputs (never errors).
    typed = classify_claims(extract_claims(normalized))
    claims = [Claim(case=case, text=t.text, source_start=t.start, source_end=t.end,
                    claim_type=t.claim_type, gate_status=t.gate_status, components=asdict(t.components))
              for t in typed]
    db.add_all(claims); db.flush()
    checkable = [c for c in claims if c.gate_status == GATE_PROCEED]
    gate_line = (f"Claim-type gate kept {len(checkable)} checkable claim(s) and typed "
                 f"{len(claims) - len(checkable)} as non-checkable (returned without veracity scoring).")

    warnings, all_items = [], []
    if scan.flagged:
        case.security_flags = [{"type": "prompt_injection_suspected", "matches": list(scan.matches)}]
        warnings.append(INJECTION_WARNING)
    else:
        retriever = FactCheckRetriever(settings.google_factcheck_api_key)
        for claim in checkable:
            result = await retriever.search(claim.text, lang.code)
            if result.warning and result.warning not in warnings:
                warnings.append(result.warning)
            for item in result.items:
                e = EvidenceItem(claim=claim, **item); db.add(e); db.flush()
                # claim_text is passed to the rubric's relevance guard only; it is
                # not a column on EvidenceItem, so it is added after the model is built.
                all_items.append({**item, "id": e.id, "claim_text": claim.text})

    finding = assess(len(checkable), all_items)
    path = [gate_line, *finding.reasoning_path]
    if scan.flagged:
        path.append("Injection heuristic flagged the input; skipped external retrieval and routed to human review.")
        finding = Finding("unverifiable", "Low",
                          "Ingested content contains a possible prompt-injection pattern. "
                          "Human review is required before any verification.", path)
    elif claims and not checkable:
        finding = Finding("unverifiable", "Low",
                          "No checkable factual claims were identified; non-checkable claims are "
                          "typed and returned for review without veracity scoring.", path)
    else:
        finding = Finding(finding.verdict, finding.confidence, finding.rationale, path)

    case.assessment = Assessment(verdict=finding.verdict, confidence=finding.confidence,
                                 rationale=finding.rationale, reasoning_path=finding.reasoning_path,
                                 evidence_ids=[x["id"] for x in all_items], rubric_version=RUBRIC_VERSION)
    case.status = CaseStatus.pending_review
    db.commit(); db.refresh(case)
    return case, warnings
