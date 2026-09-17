from dataclasses import asdict
from sqlalchemy.orm import Session
from ..config import settings
from ..models import Assessment, CaseStatus, Claim, EvidenceItem, Representation, VerificationCase
from .claims import extract_claims
from .claim_gate import GATE_PROCEED, classify_claims
from .injection import sanitize_and_scan
from .retrieval import FactCheckRetriever
from .rubric import RUBRIC_VERSION, Finding, assess
from . import reasoning, websearch, llm as llm_module
from .url_fetch import fetch_article
from .language import analyze, normalize
from .sensitivity import detect as detect_sensitivity

INJECTION_WARNING = ("Potential prompt-injection pattern detected in ingested content; "
                     "external retrieval was skipped and the case was routed to human review.")

_CONF_RANK = {"Low": 0, "Moderate": 1, "High": 2}
_VERDICT_PRIORITY = ["contradicted", "misleading", "partly_true", "mixed", "supported",
                     "mostly supported", "unverifiable"]


async def verify(db: Session, text: str | None, url: str | None) -> tuple[VerificationCase, list[str]]:
    if text is None:
        fetched = await fetch_article(str(url))
        return await _run_case(db, fetched, str(url), "url", str(url))
    return await _run_case(db, text, text, "text", None)


async def verify_normalized(db: Session, normalized: str, original_input: str, input_type: str,
                            source_url: str | None = None):
    return await _run_case(db, normalized, original_input, input_type, source_url)


def _aggregate(findings: list[Finding]) -> Finding:
    """Combine per-claim findings into one case-level finding."""
    if len(findings) == 1:
        return findings[0]
    verdicts = {f.verdict for f in findings}
    if len(verdicts) == 1:
        verdict = next(iter(verdicts))
    elif "supported" in verdicts and verdicts & {"contradicted", "misleading", "partly_true"}:
        verdict = "mixed"
    else:
        verdict = next((v for v in _VERDICT_PRIORITY if v in verdicts), "unverifiable")
    confidence = min((f.confidence for f in findings), key=lambda c: _CONF_RANK.get(c, 0))
    rationale = " ".join(f"Claim {i + 1}: {f.rationale}" for i, f in enumerate(findings))
    path = []
    for i, f in enumerate(findings):
        path.append(f"— Claim {i + 1} —")
        path.extend(f.reasoning_path)
    return Finding(verdict, confidence, rationale, path)


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

    sensitivity = detect_sensitivity(normalized)

    if scan.flagged:
        case.security_flags = [{"type": "prompt_injection_suspected", "matches": list(scan.matches)}]
        warnings.append(INJECTION_WARNING)
        finding = Finding("unverifiable", "Low",
                          "Ingested content contains a possible prompt-injection pattern. "
                          "Human review is required before any verification.",
                          [gate_line, "Injection heuristic flagged the input; skipped external "
                           "retrieval and routed to human review."])
        evidence_ids = []
    elif sensitivity.flagged:
        case.security_flags = [{"type": "sensitive_claim", "categories": list(sensitivity.categories),
                                "matches": list(sensitivity.matches)}]
        warnings.append("Politically sensitive or contested claim detected; no automated verdict is displayed before human review.")
        finding = Finding("unverifiable", "Low",
                          "This claim involves elections, political actors, identity conflict, or public order. "
                          "It requires human review before any substantive verdict is shown.",
                          [gate_line, "Sensitivity gate matched: " + ", ".join(sensitivity.categories) + ".",
                           "Skipped automated retrieval and adjudication; routed to human review without a substantive verdict."])
        evidence_ids = []
    elif claims and not checkable:
        finding = Finding("unverifiable", "Low",
                          "No checkable factual claims were identified; non-checkable claims are "
                          "typed and returned for review without veracity scoring.", [gate_line])
        evidence_ids = []
    else:
        retriever = FactCheckRetriever(settings.google_factcheck_api_key)
        web_client = websearch.build_client(settings)
        llm_client = llm_module.build_client(settings)

        per_claim_evidence: dict[str, list[dict]] = {}
        for claim in checkable:
            fc = await retriever.search(claim.text, lang.code)
            if fc.warning and fc.warning not in warnings:
                warnings.append(fc.warning)
            # Open-web evidence is only worth gathering when an LLM can reason over it.
            web_items = []
            if llm_client is not None:
                web = await reasoning.gather_web_evidence(claim.text, web_client)
                for w in web.warnings:
                    if w not in warnings:
                        warnings.append(w)
                web_items = web.items

            stored = []
            for item in [*fc.items, *web_items]:
                e = EvidenceItem(claim=claim, **item); db.add(e); db.flush()
                record = {**item, "id": e.id, "claim_text": claim.text}
                stored.append(record)
                all_items.append(record)
            per_claim_evidence[claim.id] = stored

        if llm_client is not None:
            findings, cited = [], []
            for claim in checkable:
                result = await reasoning.adjudicate_claim(
                    claim.text, per_claim_evidence[claim.id], llm_client)
                if result is None:
                    # LLM call failed for this claim; fall back to the rubric over its evidence.
                    findings.append(assess(1, per_claim_evidence[claim.id]))
                else:
                    findings.append(result.finding)
                    cited.extend(result.cited_ids)
            finding = _aggregate(findings)
            evidence_ids = cited or [x["id"] for x in all_items]
        else:
            finding = assess(len(checkable), all_items)
            finding = Finding(finding.verdict, finding.confidence, finding.rationale,
                              [gate_line, *finding.reasoning_path])
            evidence_ids = [x["id"] for x in all_items]

        if llm_client is not None:
            finding = Finding(finding.verdict, finding.confidence, finding.rationale,
                              [gate_line, *finding.reasoning_path])

    case.assessment = Assessment(verdict=finding.verdict, confidence=finding.confidence,
                                 rationale=finding.rationale, reasoning_path=finding.reasoning_path,
                                 evidence_ids=evidence_ids, rubric_version=RUBRIC_VERSION)
    case.status = CaseStatus.pending_review
    db.commit(); db.refresh(case)
    return case, warnings
