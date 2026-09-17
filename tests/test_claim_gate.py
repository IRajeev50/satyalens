from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.claim_gate import GATE_NON_CHECKABLE, GATE_PROCEED, classify_claim


def test_classifies_checkable_fact_and_extracts_components():
    t = classify_claim("According to Reuters, the RBI increased the repo rate by 50 basis points in 2024.")
    assert t.claim_type == "checkable_fact"
    assert t.gate_status == GATE_PROCEED
    assert t.components.authority == "Reuters"
    assert t.components.quantity == "50"
    assert t.components.time == "2024"
    assert t.components.predicate == "increased"
    assert "RBI" in (t.components.subject or "")
    assert t.components.modality == "declarative"


def test_classifies_prediction():
    t = classify_claim("India's GDP will grow 7 percent in 2027.")
    assert t.claim_type == "prediction"
    assert t.gate_status == GATE_NON_CHECKABLE
    assert t.components.modality == "predictive"


def test_classifies_opinion():
    t = classify_claim("I believe the minister should resign immediately.")
    assert t.claim_type == "opinion"
    assert t.gate_status == GATE_NON_CHECKABLE


def test_classifies_satire():
    t = classify_claim("Satire: Local man declares himself the new RBI governor.")
    assert t.claim_type == "satire"
    assert t.gate_status == GATE_NON_CHECKABLE


def test_classifies_subjective():
    t = classify_claim("This biryani is very tasty.")
    assert t.claim_type == "subjective"
    assert t.gate_status == GATE_NON_CHECKABLE


def test_classifies_not_a_claim():
    assert classify_claim("What time does the booth close tomorrow?").claim_type == "not_a_claim"
    assert classify_claim("Please share this with everyone").claim_type == "not_a_claim"


def test_gate_in_pipeline_types_claims_and_skips_retrieval_for_non_checkable():
    with TestClient(app) as c:
        r = c.post("/api/verify", json={"text": "I believe the minister is the best. Delhi has 20 new centres."})
        assert r.status_code == 200
        body = r.json()
        by_type = {c["claim_type"]: c for c in body["claims"]}
        assert "opinion" in by_type and "checkable_fact" in by_type
        assert by_type["opinion"]["gate_status"] == "non_checkable"
        assert by_type["opinion"]["evidence"] == []
        assert by_type["checkable_fact"]["gate_status"] == "proceed"
        assert any("gate" in step.lower() for step in body["assessment"]["reasoning_path"])


def test_all_non_checkable_submission_stays_unverifiable_for_review():
    with TestClient(app) as c:
        r = c.post("/api/verify", json={"text": "I believe the policy will fail badly."})
        assert r.status_code == 200
        body = r.json()
        assert body["assessment"]["verdict"] == "unverifiable"
        assert body["status"] == "pending_review"
        assert all(x["gate_status"] == "non_checkable" for x in body["claims"])


def test_hindi_and_hinglish_cues():
    assert classify_claim("मुझे लगता है कि यह नीति बेकार है।").claim_type == "opinion"
    assert classify_claim("योजना 2030 तक 2 करोड़ नौकरियां देगी।").claim_type == "prediction"
    assert classify_claim("मौसम बहुत अच्छा है।").claim_type == "subjective"
    assert classify_claim("बिहार विधानसभा में 243 सीटें हैं।").claim_type == "checkable_fact"
