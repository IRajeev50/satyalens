"""Deterministic claim-type gate (Phase 7).

Every atomic claim is classified before any verification work. Only
``checkable_fact`` claims proceed to evidence retrieval and veracity
scoring. All other types are first-class, typed outputs returned without
a verdict - they are not errors and are never silently dropped.

An ``LLM_*`` seam exists in settings for later model-assisted typing;
this module stays deterministic so behaviour is auditable and testable.
"""
import re
from dataclasses import dataclass

CLAIM_TYPES = ("checkable_fact", "prediction", "opinion", "satire", "subjective", "not_a_claim")
GATE_PROCEED = "proceed"
GATE_NON_CHECKABLE = "non_checkable"

_SATIRE = re.compile(r"\b(satire|spoof|parody)\b|#satire\b|\b(faking news|babylon bee|the onion)\b", re.I)
_OPINION = re.compile(
    r"\b(i think|i believe|i feel|in my (?:honest |humble )?opinion|imho|personally|"
    r"(?:we|they|he|she|you) should|should (?:all|resign|go|stay)|must (?:resign|go|be stopped)|"
    r"shameful|disgraceful|मुझे लगता|मेरी राय|मेरा मानना|होना चाहिए|चाहिए)", re.I)
_SUBJECTIVE = re.compile(
    r"\b(is|are|was|were|looks?|seems?|feels?|sounds?|tastes?)\s+(?:so |very |really |too |quite |absolutely )?"
    r"(beautiful|ugly|delicious|tasty|boring|amazing|awesome|awful|terrible|horrible|wonderful|"
    r"expensive|cheap|overrated|underrated|brilliant|stupid|best|worst)\b|"
    r"(?:बहुत|सबसे|काफी)\s+(?:अच्छा|अच्छी|बुरा|बुरी|सुंदर|खराब|महंगा|महंगी|सस्ता|सस्ती|बेहतरीन|बेकार|शानदार)", re.I)
_FUTURE = re.compile(
    r"\b(will|won't|would|shall|is going to|are going to|expected to|projected to|set to|"
    r"likely to|unlikely to|poised to|forecast(?:ed)?(?: to)?|predicted to|"
    r"होगा|होगी|होंगे|करेगा|करेगी|करेंगे|देगा|देगी|देंगे|बनेगा|बनेगी|आएगा|आएगी)", re.I)
_IMPERATIVE = re.compile(
    r"^\s*(?:please\s+)?(share|forward|send|post|watch|read|click|join|subscribe|stop|help|pray|retweet|viral)\b", re.I)
_GREETING = re.compile(r"^\s*(hi|hello|hey|good (?:morning|afternoon|evening|night)|namaste|namaskar|happy \w+|jai \w+)\b", re.I)

_AUTHORITY = re.compile(
    r"\b(?:said|says|according to|reported by|told|announced by|tweeted by|claimed by)\s+"
    r"([A-Z][\w.\-]*(?:\s+[A-Z][\w.\-]*){0,3})", re.I)
_TIME = re.compile(
    r"\b(?:(?:19|20)\d{2}|(?:january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+\d{1,2}(?:,\s*(?:19|20)\d{2})?|today|yesterday|tomorrow|tonight|"
    r"last\s+(?:week|month|year|night|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"this\s+(?:week|month|year|morning|evening)|next\s+(?:week|month|year)|"
    r"(?:mon|tues|wednes|thurs|fri|satur|sun)day)\b", re.I)
_QUANTITY = re.compile(
    r"(?:₹|rs\.?|inr|\$|usd|eur|€|£)?\s*\d[\d,]*(?:\.\d+)?\s*"
    r"(?:crore|lakh|million|billion|trillion|thousand|hundred|percent|%|km|kilometres?|miles?|"
    r"kg|tonnes?|tons?|litres?|liters?|degrees?|°c|°f|seats?|wickets?|runs?)?", re.I)
_PLACE = re.compile(r"\b(?:in|at|near|from|across)\s+([A-Z][A-Za-z.]*(?:\s+(?:of\s+)?[A-Z][A-Za-z.]*){0,2})")
_VERB = re.compile(
    r"\b(is|are|was|were|has|have|had|will|would|announced|said|says|reported|increased|decreased|won|lost|"
    r"launched|banned|approved|died|killed|arrested|elected|became|made|took|gave|found|shows?|claims?|"
    r"confirmed|denied|tested|recovered|crossed|reached)\b", re.I)


@dataclass(frozen=True)
class ClaimComponents:
    subject: str | None
    predicate: str | None
    object: str | None
    quantity: str | None
    place: str | None
    time: str | None
    authority: str | None
    modality: str


@dataclass(frozen=True)
class TypedClaim:
    text: str
    start: int
    end: int
    claim_type: str
    components: ClaimComponents
    gate_status: str
    rationale: str


def _components(text: str, modality: str) -> ClaimComponents:
    subject = predicate = obj = None
    verb = _VERB.search(text)
    if verb:
        head = text[: verb.start()].strip(" ,:;\"'")
        subject = head or None
        predicate = verb.group(0)
        tail = text[verb.end():].strip(" .,:;\"'")
        obj = tail or None
    authority = _AUTHORITY.search(text)
    time = _TIME.search(text)
    quantity = _QUANTITY.search(text)
    place = _PLACE.search(text)
    return ClaimComponents(
        subject=subject,
        predicate=predicate,
        object=obj,
        quantity=quantity.group(0).strip() if quantity else None,
        place=place.group(1).strip() if place else None,
        time=time.group(0) if time else None,
        authority=authority.group(1).strip() if authority else None,
        modality=modality,
    )


def classify_claim(text: str, start: int = 0, end: int | None = None) -> TypedClaim:
    """Classify one atomic claim. Deterministic heuristics; conservative by design.

    A wrong ``checkable_fact`` on opinionated content is worse than a wrong
    ``non_checkable`` on a real fact, so ambiguous cases fall to review.
    """
    end = len(text) if end is None else end
    stripped = text.strip()

    if stripped.endswith("?"):
        kind, modality, why = "not_a_claim", "interrogative", "A question carries no assertable proposition."
    elif _GREETING.match(stripped) or _IMPERATIVE.match(stripped):
        kind, modality, why = "not_a_claim", "imperative", "A greeting, plea or call to action carries no assertable proposition."
    elif len(stripped.split()) < 3 and not _QUANTITY.search(stripped):
        kind, modality, why = "not_a_claim", "fragment", "Too little propositional content to verify."
    elif _SATIRE.search(stripped):
        kind, modality, why = "satire", "declarative", "Explicit satire/parody marker found; satire is not fact-checked as news."
    elif _OPINION.search(stripped):
        kind, modality, why = "opinion", "evaluative", "First-person belief or prescriptive language; not externally checkable."
    elif _SUBJECTIVE.search(stripped) and not _QUANTITY.search(stripped):
        kind, modality, why = "subjective", "evaluative", "Evaluative predication without measurable content."
    elif _FUTURE.search(stripped):
        kind, modality, why = "prediction", "predictive", "Future-tense or forecast language; only its source and framing can be checked, not the outcome."
    else:
        kind, modality, why = "checkable_fact", "declarative", "Declarative claim with fact cues; proceeds to evidence retrieval."

    gate = GATE_PROCEED if kind == "checkable_fact" else GATE_NON_CHECKABLE
    return TypedClaim(text=text, start=start, end=end, claim_type=kind,
                      components=_components(text, modality), gate_status=gate, rationale=why)


def classify_claims(extracted) -> list[TypedClaim]:
    return [classify_claim(c.text, c.start, c.end) for c in extracted]
