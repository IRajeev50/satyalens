from dataclasses import dataclass
RUBRIC_VERSION = "1.0.0"

@dataclass(frozen=True)
class Finding:
    verdict: str; confidence: str; rationale: str; reasoning_path: list[str]

POSITIVE = ("true", "correct", "accurate", "supported")
NEGATIVE = ("false", "incorrect", "fake", "misleading", "pants on fire")

def assess(claim_count: int, evidence: list[dict]) -> Finding:
    path = [f"Split submission into {claim_count} atomic claim(s).", f"Retrieved {len(evidence)} prior fact-check evidence item(s)."]
    if not evidence:
        path += ["No external evidence was available.", "Applied abstention rule: lack of evidence is not evidence of falsity."]
        return Finding("unverifiable", "Low", "No adequate evidence was retrieved. Human review is required before relying on this result.", path)
    ratings = [str(x.get("rating") or "").lower() for x in evidence]
    pos = sum(any(t in r for t in POSITIVE) and not any(t in r for t in NEGATIVE) for r in ratings)
    neg = sum(any(t in r for t in NEGATIVE) for r in ratings)
    unknown = len(ratings) - pos - neg
    path.append(f"Mapped published ratings: {pos} supporting, {neg} contradicting, {unknown} unclear.")
    if pos and neg: verdict, rationale = "mixed", "Published fact checks disagree; inspect claim scope, dates and sources."
    elif neg >= 2: verdict, rationale = "contradicted", "Multiple retrieved fact checks rate matching claims as false or misleading."
    elif neg == 1: verdict, rationale = "misleading", "A retrieved fact check disputes or materially qualifies the claim."
    elif pos >= 2: verdict, rationale = "supported", "Multiple retrieved fact checks support the claim."
    elif pos == 1: verdict, rationale = "mostly supported", "One matching published fact check supports the claim, but independent coverage is limited."
    else: verdict, rationale = "unverifiable", "Retrieved items did not provide a usable rating."
    confidence = "Moderate" if (pos + neg) >= 2 else "Low"
    path += [f"Applied rubric {RUBRIC_VERSION}: {verdict} / {confidence}.", "Queued the draft for human review."]
    return Finding(verdict, confidence, rationale, path)
