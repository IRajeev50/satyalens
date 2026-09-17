import re
from dataclasses import dataclass

@dataclass(frozen=True)
class ExtractedClaim:
    text: str
    start: int
    end: int

_FACT_CUES = re.compile(r"\b(is|are|was|were|has|have|had|will|announced|said|reported|increased|decreased|won|launched|banned|approved)\b|\d", re.I)

def extract_claims(text: str, limit: int = 8) -> list[ExtractedClaim]:
    """Deterministic Phase 1 extraction. Preserves exact spans; rejects questions/opinion-like fragments."""
    clean = re.sub(r"[ \t]+", " ", text.strip())
    parts = list(re.finditer(r"[^.!?\n]+(?:[.!?]|$)", clean))
    claims: list[ExtractedClaim] = []
    for match in parts:
        raw = match.group(0)
        stripped = raw.strip()
        if len(stripped) < 12 or stripped.endswith("?") or not _FACT_CUES.search(stripped):
            continue
        lead = len(raw) - len(raw.lstrip())
        tail = stripped.rstrip(".! ")
        start = match.start() + lead
        claims.append(ExtractedClaim(tail, start, start + len(tail)))
        if len(claims) >= limit: break
    if not claims and len(clean) >= 3:
        claims.append(ExtractedClaim(clean[:500].rstrip(".! "), 0, min(len(clean.rstrip(".! ")), 500)))
    return claims
