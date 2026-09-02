def test_create_person_requires_name(client):
    resp = client.post("/api/v1/people", json={"name": ""})
    assert resp.status_code == 422


def test_patch_person_name_null_returns_422(client):
    created = client.post("/api/v1/people", json={"name": "Аян"})
    person_id = created.json()["id"]

    resp = client.patch(f"/api/v1/people/{person_id}", json={"name": None})
    assert resp.status_code == 422


def test_patch_person_omitting_name_keeps_it(client):
    created = client.post("/api/v1/people", json={"name": "Аян"})
    person_id = created.json()["id"]

    resp = client.patch(f"/api/v1/people/{person_id}", json={"notes": "VIP"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Аян"
    assert body["notes"] == "VIP"
