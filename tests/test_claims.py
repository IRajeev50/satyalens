from backend.app.services.claims import extract_claims

def test_extracts_atomic_claims_and_spans():
    text = "The ministry launched Scheme X in 2024. Critics dislike it. Delhi has 20 new centres."
    claims = extract_claims(text)
    assert [x.text for x in claims] == ["The ministry launched Scheme X in 2024", "Delhi has 20 new centres"]
    assert all(text[x.start:x.end] == x.text for x in claims)

def test_fallback_keeps_short_unclassified_submission():
    assert extract_claims("Moon landing hoax")[0].text == "Moon landing hoax"
