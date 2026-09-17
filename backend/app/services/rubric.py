import re
from dataclasses import dataclass

# 1.1.0: rating normalization is negation-aware (e.g. "Not true", "Unsupported"
# are contradictions, not support) and evidence must be lexically relevant to the
# claim before its rating counts. See tests/test_rubric.py.
RUBRIC_VERSION = "1.1.0"

# Minimum share of the claim's content tokens that must appear in an evidence
# item before its published rating is allowed to move the verdict. A published
# fact check returned by a keyword search is only relevant if it is actually
# about (roughly) the same claim; otherwise a "False" rating on a different claim
# that merely shares keywords would contaminate this verdict.
MIN_RELEVANCE = 0.30


@dataclass(frozen=True)
class Finding:
    verdict: str; confidence: str; rationale: str; reasoning_path: list[str]


# --- Rating normalization -----------------------------------------------------
# Published textualRating strings map to one of: support | contradict | mixed |
# unknown. Order matters: mixed and contradiction (which includes negations like
# "not true" and "un-" prefixes) are checked BEFORE support, so that "unsupported"
# and "untrue" never fall through to the substring "supported" / "true".

_MIXED = (
    "half true", "half-true", "half right", "partly true", "partially true",
    "partly false", "partially false", "half false", "half-false", "mixture",
    "mixed", "some truth", "half correct",
)
_CONTEXT = ("missing context", "needs context", "lacks context", "out of context",
            "misleading context", "flawed reasoning")
_CONTRADICT = (
    "false", "fake", "hoax", "incorrect", "inaccurate", "misleading",
    "misattributed", "miscaptioned", "not true", "untrue", "unsupported",
    "no evidence", "baseless", "debunked", "fabricated", "doctored", "distort",
    "pants on fire", "not correct", "misrepresent", "exaggerat", "scam",
    "altered", "manipulated", "wrong", "not real",
)
_UNKNOWN = ("unproven", "unverified", "unverifiable", "insufficient evidence",
            "research in progress", "developing", "no rating")
_SUPPORT = ("true", "correct", "accurate", "supported", "legit", "confirmed",
            "verified", "authentic", "real", "genuine")


def normalize_rating(rating: str | None) -> str:
    """Map a published fact-check rating to support|contradict|mixed|unknown.

    Negation-aware and order-sensitive: contradiction and mixed cues win over the
    bare "true"/"supported" substrings so that "Not true", "Untrue", "Unsupported"
    and "Half true" are never counted as support.
    """
    r = re.sub(r"\s+", " ", (rating or "").strip().lower())
    if not r:
        return "unknown"
    if any(cue in r for cue in _MIXED):
        return "mixed"
    if any(cue in r for cue in _CONTEXT):
        return "mixed"
    if any(cue in r for cue in _CONTRADICT):
        return "contradict"
    if any(cue in r for cue in _UNKNOWN):
        return "unknown"
    if any(cue in r for cue in _SUPPORT):
        return "support"
    return "unknown"


# --- Relevance guard ----------------------------------------------------------
_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "at", "for", "and", "or", "is",
    "are", "was", "were", "be", "has", "have", "had", "that", "this", "it",
    "as", "by", "with", "from", "will", "not", "no", "but", "if", "so",
}


def _tokens(text: str) -> set[str]:
    # Keep Latin and Devanagari (and other Indic block) word characters; drop
    # short tokens and stopwords. Cross-script overlap still works when the claim
    # and the evidence quote are in the same language.
    raw = re.findall(r"[0-9A-Za-zऀ-෿]+", (text or "").lower())
    return {t for t in raw if len(t) > 2 and t not in _STOPWORDS}


def relevance(claim_text: str, item: dict) -> float:
    """Share of the claim's content tokens that appear in the evidence item.

    0.0 means no lexical overlap (treat as unrelated); 1.0 means every content
    token of the claim appears in the evidence quote/title.
    """
    claim_tokens = _tokens(claim_text)
    if not claim_tokens:
        return 0.0
    ev_tokens = _tokens(" ".join(str(item.get(k) or "") for k in ("quote", "source_title")))
    if not ev_tokens:
        return 0.0
    return len(claim_tokens & ev_tokens) / len(claim_tokens)


def assess(claim_count: int, evidence: list[dict]) -> Finding:
    path = [f"Split submission into {claim_count} atomic claim(s).",
            f"Retrieved {len(evidence)} prior fact-check evidence item(s)."]

    # Relevance guard: an item that carries the claim text it was retrieved for
    # must be lexically relevant to it before its rating counts. Items without a
    # claim_text key (e.g. direct unit-test fixtures) are counted as-is.
    considered, dropped = [], 0
    for item in evidence:
        claim_text = item.get("claim_text")
        if claim_text is not None and relevance(claim_text, item) < MIN_RELEVANCE:
            dropped += 1
            continue
        considered.append(item)
    if dropped:
        path.append(f"Set aside {dropped} retrieved item(s) that did not lexically match "
                    f"their claim (below relevance {MIN_RELEVANCE:.2f}); they do not affect the verdict.")

    if not considered:
        reason = ("No external evidence was available." if not evidence
                  else "Retrieved items did not match the claim closely enough to be usable.")
        path += [reason, "Applied abstention rule: lack of evidence is not evidence of falsity."]
        return Finding("unverifiable", "Low",
                       "No adequate matching evidence was retrieved. Human review is required before "
                       "relying on this result.", path)

    labels = [normalize_rating(x.get("rating")) for x in considered]
    pos = labels.count("support")
    neg = labels.count("contradict")
    mixed = labels.count("mixed")
    unknown = labels.count("unknown")
    path.append(f"Normalized published ratings: {pos} supporting, {neg} contradicting, "
                f"{mixed} mixed/qualified, {unknown} unclear.")

    if (pos and neg) or (mixed and (pos or neg)):
        verdict, rationale = "mixed", "Published fact checks disagree or qualify the claim; inspect scope, dates and sources."
    elif neg >= 2:
        verdict, rationale = "contradicted", "Multiple retrieved fact checks rate matching claims as false or misleading."
    elif neg == 1:
        verdict, rationale = "misleading", "A retrieved fact check disputes or materially qualifies the claim."
    elif pos >= 2:
        verdict, rationale = "supported", "Multiple retrieved fact checks support the claim."
    elif pos == 1:
        verdict, rationale = "mostly supported", "One matching published fact check supports the claim, but independent coverage is limited."
    elif mixed:
        verdict, rationale = "mixed", "Retrieved fact checks rate the claim as partly true or missing context."
    else:
        verdict, rationale = "unverifiable", "Retrieved items did not provide a usable rating."

    confidence = "Moderate" if (pos + neg) >= 2 else "Low"
    path += [f"Applied rubric {RUBRIC_VERSION}: {verdict} / {confidence}.",
             "Queued the draft for human review."]
    return Finding(verdict, confidence, rationale, path)
