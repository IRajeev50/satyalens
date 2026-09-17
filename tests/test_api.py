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
