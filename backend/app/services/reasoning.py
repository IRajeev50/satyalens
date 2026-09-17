"""Per-claim reasoning: open-web evidence gathering + grounded LLM adjudication.

Keeps persistence in the pipeline. This module (1) fetches and DEFENDS web
snippets (each is sanitized and injection-scanned; attacker-shaped snippets are
dropped, never sent to the LLM), and (2) turns an LLM adjudication over stored
evidence into a grounded finding, downgrading any ungrounded verdict to
``unverifiable``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .injection import sanitize_and_scan
from .llm import LLMClient
from .rubric import Finding
from .websearch import WebSearchClient

_MAX_SNIPPET = 1200


@dataclass
class WebEvidence:
    items: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dropped_injection: int = 0


@dataclass(frozen=True)
class ClaimResult:
    finding: Finding
    cited_ids: list[str]


async def gather_web_evidence(query: str, client: WebSearchClient | None) -> WebEvidence:
    """Search the open web and return sanitized, injection-screened evidence dicts."""
    out = WebEvidence()
    if client is None:
        return out
    result = await client.search(query)
    if result.warning:
        out.warnings.append(result.warning)
    for item in result.items:
        cleaned, scan = sanitize_and_scan(item.get("quote", ""), max_length=_MAX_SNIPPET)
        if scan.flagged:
            # A search snippet carrying an injection payload is discarded, not sent to the LLM.
            out.dropped_injection += 1
            continue
        out.items.append({**item, "quote": cleaned})
    if out.dropped_injection:
        out.warnings.append(f"Discarded {out.dropped_injection} web snippet(s) containing "
                            f"prompt-injection patterns before reasoning.")
    return out


async def adjudicate_claim(claim_text: str, evidence_with_ids: list[dict],
                           llm_client: LLMClient | None) -> ClaimResult | None:
    """Adjudicate one claim over already-stored evidence (each dict carries an 'id').

    Returns None when no LLM is configured (caller uses the fact-check rubric
    fallback). Enforces grounding: a non-abstaining verdict with no valid
    citation is downgraded to ``unverifiable``.
    """
    if llm_client is None:
        return None
    adj = await llm_client.adjudicate(claim_text, evidence_with_ids)
    if adj is None:
        return None

    cited_ids = [evidence_with_ids[i]["id"] for i in adj.citations
                 if 0 <= i < len(evidence_with_ids)]
    path = [
        f"Reasoned over {len(evidence_with_ids)} evidence item(s) "
        f"({sum(1 for e in evidence_with_ids if (e.get('raw') or {}).get('source_type') == 'web_search')} "
        f"from open-web search).",
    ]
    verdict, confidence, rationale = adj.verdict, adj.confidence, adj.rationale
    if verdict != "unverifiable" and not cited_ids:
        # Ungrounded: the model gave a verdict but cited nothing valid. Do not trust it.
        path.append("Model returned a verdict without grounding it in provided evidence; "
                    "downgraded to unverifiable and routed to human review.")
        verdict, confidence = "unverifiable", "Low"
        rationale = ("The automated reasoning did not ground its conclusion in the retrieved "
                     "evidence, so no verdict is asserted. " + rationale)
    else:
        path.append(f"LLM adjudication: {verdict} / {confidence}; cited {len(cited_ids)} item(s).")
        for kp in adj.key_points:
            path.append(f"Key point: {kp}")
    path.append("Queued the draft for human review.")
    return ClaimResult(Finding(verdict, confidence, rationale, path), cited_ids)
