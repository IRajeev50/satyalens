from fastapi.testclient import TestClient
from backend.app.main import app

def test_verify_text_end_to_end_without_keys():
    with TestClient(app) as c:
        r=c.post('/api/verify',json={'text':'The government launched Scheme X in 2024.'})
        assert r.status_code==200
        body=r.json(); assert body['assessment']['verdict']=='unverifiable'; assert body['status']=='pending_review'; assert body['claims']

def test_status_reports_evidence_source_without_leaking_key():
    with TestClient(app) as c:
        r=c.get('/api/status')
        assert r.status_code==200
        body=r.json()
        # keys present; no secret value is ever returned
        assert set(body)=={'factcheck_configured','evidence_source'}
        assert isinstance(body['factcheck_configured'],bool)
        assert body['evidence_source'] in (None,'google_factcheck')
