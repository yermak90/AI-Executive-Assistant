def test_create_project_requires_name(client):
    resp = client.post("/api/v1/projects", json={"name": ""})
    assert resp.status_code == 422


def test_patch_project_name_null_returns_422(client):
    created = client.post("/api/v1/projects", json={"name": "Детский сад"})
    project_id = created.json()["id"]

    resp = client.patch(f"/api/v1/projects/{project_id}", json={"name": None})
    assert resp.status_code == 422


def test_patch_project_is_active_null_returns_422(client):
    created = client.post("/api/v1/projects", json={"name": "Детский сад"})
    project_id = created.json()["id"]

    resp = client.patch(f"/api/v1/projects/{project_id}", json={"is_active": None})
    assert resp.status_code == 422


def test_patch_project_deactivate(client):
    created = client.post("/api/v1/projects", json={"name": "Детский сад"})
    project_id = created.json()["id"]

    resp = client.patch(f"/api/v1/projects/{project_id}", json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
