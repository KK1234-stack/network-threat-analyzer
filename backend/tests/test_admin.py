def test_retrain_status_accessible_to_admin(client, admin_headers):
    resp = client.get("/admin/retrain/status", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "idle"
    assert data["metrics"] is None
    assert data["error"] is None


def test_retrain_status_forbidden_for_non_admin(client, auth_headers):
    resp = client.get("/admin/retrain/status", headers=auth_headers)
    assert resp.status_code == 403
    assert "Admin" in resp.json()["detail"]


def test_retrain_status_requires_auth(client):
    resp = client.get("/admin/retrain/status")
    assert resp.status_code == 401


def test_retrain_trigger_forbidden_for_non_admin(client, auth_headers):
    resp = client.post("/admin/retrain", headers=auth_headers)
    assert resp.status_code == 403


def test_retrain_trigger_requires_auth(client):
    resp = client.post("/admin/retrain")
    assert resp.status_code == 401
