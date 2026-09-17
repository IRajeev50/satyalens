import pytest
from backend.app.services.rubric import assess, normalize_rating, relevance

def test_abstains_without_evidence():
    f=assess(1,[]); assert (f.verdict,f.confidence)==("unverifiable","Low")
def test_maps_two_false_ratings_to_contradicted():
    f=assess(1,[{"rating":"False"},{"rating":"Incorrect"}]); assert (f.verdict,f.confidence)==("contradicted","Moderate")
def test_maps_disagreement_to_mixed():
    assert assess(1,[{"rating":"True"},{"rating":"False"}]).verdict=="mixed"


# --- #1: rating normalization is negation-aware --------------------------------

@pytest.mark.parametrize("rating,expected", [
    ("True", "support"), ("Mostly true", "support"), ("Correct", "support"),
    ("Accurate", "support"), ("Verified", "support"),
    ("False", "contradict"), ("Mostly false", "contradict"), ("Incorrect", "contradict"),
    ("Misleading", "contradict"), ("Pants on Fire", "contradict"),
    # the exact strings the old substring logic mis-mapped to support:
    ("Not true", "contradict"), ("Untrue", "contradict"), ("Unsupported", "contradict"),
    # partial / qualified:
    ("Half true", "mixed"), ("Partly false", "mixed"), ("Missing context", "mixed"),
    # genuinely open:
    ("Unproven", "unknown"), ("", "unknown"), (None, "unknown"),
])
def test_normalize_rating(rating, expected):
    assert normalize_rating(rating) == expected

def test_negated_rating_is_not_counted_as_support():
    # A relevant fact check rated "Not true" must dispute the claim, never support it.
    claim = "The government gave fifty thousand rupees to every farmer in 2026"
    item = {"rating": "Not true", "quote": claim, "source_title": "Fact check on farmer payout",
            "claim_text": claim}
    verdict = assess(1, [item]).verdict
    assert verdict == "misleading"          # one contradicting item
    assert verdict not in ("supported", "mostly supported")


# --- #1: relevance guard -------------------------------------------------------

def test_relevance_scores_overlap():
    claim = "Reserve Bank kept the repo rate unchanged in 2026"
    assert relevance(claim, {"quote": "Reserve Bank kept the repo rate unchanged"}) >= 0.30
    assert relevance(claim, {"quote": "A bridge collapsed in another city"}) < 0.30

def test_irrelevant_evidence_is_dropped_not_counted():
    # Evidence rated "False" but about a different claim must not contaminate the verdict.
    claim = "The Reserve Bank kept the repo rate unchanged in 2026"
    off_topic = {"rating": "False", "quote": "Aliens landed near the India Gate last night",
                 "source_title": "UFO hoax debunked", "claim_text": claim}
    f = assess(1, [off_topic])
    assert f.verdict == "unverifiable"      # dropped -> nothing usable -> abstain
    assert any("Set aside" in step for step in f.reasoning_path)

def test_relevant_evidence_still_counts():
    claim = "The Reserve Bank kept the repo rate unchanged in 2026"
    on_topic = {"rating": "True", "quote": "Reserve Bank kept the repo rate unchanged in 2026",
                "source_title": "RBI policy", "claim_text": claim}
    assert assess(1, [on_topic]).verdict == "mostly supported"
