"""Per-claim evidence gathering and grounded LLM adjudication."""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from .injection import sanitize_and_scan
from .llm import LLMClient
from .rubric import Finding, MIN_RELEVANCE, normalize_rating, relevance
from .url_fetch import fetch_article
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
    """Return defended search evidence, verifying result pages for real clients.

    Search snippets are discovery leads, not source content. For the production
    client we fetch each public HTML result and replace the snippet with defended
    page text when possible. Failed fetches remain explicitly unverified and are
    treated as weak evidence by adjudication.
    """
    out = WebEvidence()
    if client is None:
        return out
    result = await client.search(query)
    if result.warning:
        out.warnings.append(result.warning)
    for item in result.items:
        candidate = dict(item)
        raw = dict(candidate.get("raw") or {})
        raw["content_verified"] = False
        # Fakes stay deterministic. Real provider results are source-verified.
        if isinstance(client, WebSearchClient):
            try:
                page = await fetch_article(candidate.get("source_url", ""))
                candidate["quote"] = page
                raw["content_verified"] = True
            except Exception as exc:  # a blocked/non-HTML source is a weak lead, never a fatal error
                raw["fetch_error"] = type(exc).__name__
        cleaned, scan = sanitize_and_scan(candidate.get("quote", ""), max_length=_MAX_SNIPPET)
        if scan.flagged:
            out.dropped_injection += 1
            continue
        candidate["quote"] = cleaned
        candidate["raw"] = raw
        out.items.append(candidate)
    if out.dropped_injection:
        out.warnings.append(f"Discarded {out.dropped_injection} web snippet(s) containing prompt-injection patterns before reasoning.")
    return out


def _domain(item: dict) -> str:
    try:
        return (urlparse(item.get("source_url") or "").hostname or "").lower()
    except ValueError:
        return ""


def _fitness(claim_text: str, item: dict) -> tuple[bool, bool, str]:
    """Return (substantively_relevant, strong_source, explanation)."""
    score = relevance(claim_text, item)
    if score < MIN_RELEVANCE:
        return False, False, f"lexical relevance {score:.2f} is below {MIN_RELEVANCE:.2f}"
    raw = item.get("raw") or {}
    source_type = raw.get("source_type")
    if source_type == "web_search":
        verified = bool(raw.get("content_verified"))
        return True, verified, ("fetched source content" if verified else "unverified search snippet")
    # Fact-check evidence has editorial source fitness only when its published
    # rating is usable; the query echo alone is not proof.
    rated = normalize_rating(item.get("rating")) != "unknown"
    return True, rated, ("published fact-check rating" if rated else "unrated related item")


def _confidence_cap(items: list[dict], strong: list[dict]) -> str:
    independent = len({_domain(x) for x in items if _domain(x)})
    strong_independent = len({_domain(x) for x in strong if _domain(x)})
    if len(strong) >= 2 and strong_independent >= 2:
        return "High"
    if strong or (len(items) >= 2 and independent >= 2):
        return "Moderate"
    return "Low"

async def adjudicate_claim(claim_text: str, evidence_with_ids: list[dict],
                           llm_client: LLMClient | None) -> ClaimResult | None:
    if llm_client is None:
        return None
    adj = await llm_client.adjudicate(claim_text, evidence_with_ids)
    if adj is None:
        return None

    valid = [(i, evidence_with_ids[i], _fitness(claim_text, evidence_with_ids[i]))
             for i in adj.citations if 0 <= i < len(evidence_with_ids)]
    usable = [(i, item, fit) for i, item, fit in valid if fit[0]]
    rejected = len(valid) - len(usable)
    cited_ids = [item["id"] for _, item, _ in usable]
    path = [f"Reasoned over {len(evidence_with_ids)} evidence item(s)."]
    if rejected:
        path.append(f"Rejected {rejected} cited item(s) that did not substantively match the claim.")
    verdict, confidence, rationale = adj.verdict, adj.confidence, adj.rationale
    if verdict != "unverifiable" and not usable:
        path.append("Model returned a verdict without grounding it in substantively matching evidence; downgraded to unverifiable and routed to human review.")
        verdict, confidence = "unverifiable", "Low"
        rationale = "The cited material did not substantively match the claim, so no automated verdict is asserted. " + rationale
        cited_ids = []
    else:
        strong = [item for _, item, fit in usable if fit[1]]
        cap = _confidence_cap([item for _, item, _ in usable], strong)
        order = {"Low": 0, "Moderate": 1, "High": 2}
        if order.get(confidence, 0) > order[cap]:
            path.append(f"Capped confidence from {confidence} to {cap} based on evidence quality, count and source independence.")
            confidence = cap
        path.append(f"LLM adjudication: {verdict} / {confidence}; accepted {len(cited_ids)} citation(s).")
        for kp in adj.key_points:
            path.append(f"Key point: {kp}")
    path.append("Queued the draft for human review.")
    return ClaimResult(Finding(verdict, confidence, rationale, path), cited_ids)
