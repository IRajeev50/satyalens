from fastapi.testclient import TestClient
from backend.app.main import app

def test_verify_text_end_to_end_without_keys():
    with TestClient(app) as c:
        r=c.post('/api/verify',json={'text':'The government launched Scheme X in 2024.'})
        assert r.status_code==200
        body=r.json(); assert body['assessment']['verdict']=='unverifiable'; assert body['status']=='pending_review'; assert body['claims']
