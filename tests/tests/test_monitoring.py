from fastapi.testclient import TestClient
from backend.app.main import app

def test_monitor_lifecycle_keyless():
    with TestClient(app) as c:
        made=c.post('/api/monitors',json={'query':'scheme launch India','language':'en'}); assert made.status_code==200
        mid=made.json()['id']; run=c.post(f'/api/monitors/{mid}/run'); assert run.status_code==200 and run.json()['result_count']==0
        paused=c.post(f'/api/monitors/{mid}/pause'); assert paused.json()['status']=='paused'
