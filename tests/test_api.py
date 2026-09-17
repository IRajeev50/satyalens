from fastapi.testclient import TestClient
from backend.app.main import app

def test_verify_text_end_to_end_without_keys():
    with TestClient(app) as c:
        r=c.post('/api/verify',json={'text':'The government launched Scheme X in 2024.'})
        assert r.status_code==200
        body=r.json(); assert body['assessment']['verdict']=='unverifiable'; assert body['status']=='pending_review'; assert body['claims']

def test_status_reports_sources_without_leaking_keys():
    with TestClient(app) as c:
        r=c.get('/api/status')
        assert r.status_code==200
        body=r.json()
        assert set(body)=={'factcheck_configured','websearch_configured','llm_configured',
                           'reasoning_enabled','evidence_sources'}
        for k in ('factcheck_configured','websearch_configured','llm_configured','reasoning_enabled'):
            assert isinstance(body[k],bool)
        assert isinstance(body['evidence_sources'],list)
        # no secret values are ever returned
        assert all('key' not in str(v).lower() for v in body.values())

def test_status_reasoning_requires_llm_and_evidence_source(monkeypatch):
    monkeypatch.setattr("backend.app.api.routes.settings.llm_api_key", "configured")
    monkeypatch.setattr("backend.app.api.routes.settings.google_factcheck_api_key", None)
    monkeypatch.setattr("backend.app.api.routes.settings.search_api_key", None)
    with TestClient(app) as c:
        assert c.get('/api/status').json()['reasoning_enabled'] is False


def test_political_claim_forced_to_human_review_without_verdict(monkeypatch):
    monkeypatch.setattr("backend.app.services.pipeline.settings.google_factcheck_api_key", "configured")
    monkeypatch.setattr("backend.app.services.pipeline.settings.search_api_key", "configured")
    monkeypatch.setattr("backend.app.services.pipeline.settings.llm_api_key", "configured")
    with TestClient(app) as c:
        body = c.post('/api/verify', json={'text': 'The election commission changed the polling date yesterday.'}).json()
    assert body['status'] == 'pending_review'
    assert body['assessment']['verdict'] == 'unverifiable'
    assert body['assessment']['confidence'] == 'Low'
    assert body['assessment']['evidence_ids'] == []
    assert any(f['type'] == 'sensitive_claim' for f in body['security_flags'])
