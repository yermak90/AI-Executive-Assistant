from datetime import timedelta

from app.core.timezone import now as tz_now


def _create_person(client, name="Аян"):
    resp = client.post("/api/v1/people", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_project(client, name="Детский сад"):
    resp = client.post("/api/v1/projects", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_commitment_generates_created_history(client):
    person_id = _create_person(client)
    project_id = _create_project(client)

    resp = client.post(
        "/api/v1/commitments",
        json={
            "title": "Получить стоимость ворот",
            "owner_person_id": person_id,
            "project_id": project_id,
            "direction": "OWED_TO_ME",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "ACTIVE"
    assert len(body["history"]) == 1
    assert body["history"][0]["event_type"] == "CREATED"


def test_commitment_with_deadline_today_appears_in_today_filter(client):
    today_deadline = tz_now().replace(hour=12, minute=0, second=0, microsecond=0)
    resp = client.post(
        "/api/v1/commitments",
        json={"title": "Today task", "direction": "I_OWE", "deadline": today_deadline.isoformat()},
    )
    commitment_id = resp.json()["id"]

    listed = client.get("/api/v1/commitments", params={"due": "today"})
    assert listed.status_code == 200
    ids = [c["id"] for c in listed.json()]
    assert commitment_id in ids


def test_commitment_with_past_deadline_is_overdue(client):
    past_deadline = tz_now() - timedelta(days=1)
    resp = client.post(
        "/api/v1/commitments",
        json={"title": "Overdue task", "direction": "TEAM", "deadline": past_deadline.isoformat()},
    )
    commitment_id = resp.json()["id"]
    assert resp.json()["is_overdue"] is True

    detail = client.get(f"/api/v1/commitments/{commitment_id}")
    assert detail.json()["is_overdue"] is True

    overdue_list = client.get("/api/v1/commitments", params={"overdue": "true"})
    ids = [c["id"] for c in overdue_list.json()]
    assert commitment_id in ids


def test_complete_commitment_sets_status_and_history(client):
    resp = client.post("/api/v1/commitments", json={"title": "Task", "direction": "I_OWE"})
    commitment_id = resp.json()["id"]

    completed = client.post(f"/api/v1/commitments/{commitment_id}/complete")
    assert completed.status_code == 200
    body = completed.json()
    assert body["status"] == "COMPLETED"
    assert body["completed_at"] is not None
    assert any(h["event_type"] == "COMPLETED" for h in body["history"])

    active_list = client.get("/api/v1/commitments", params={"status": "ACTIVE"})
    ids = [c["id"] for c in active_list.json()]
    assert commitment_id not in ids


def test_reschedule_preserves_old_and_new_deadline_in_history(client):
    old_deadline = tz_now().replace(hour=10, minute=0, second=0, microsecond=0)
    resp = client.post(
        "/api/v1/commitments",
        json={"title": "Task", "direction": "I_OWE", "deadline": old_deadline.isoformat()},
    )
    commitment_id = resp.json()["id"]

    new_deadline = tz_now() + timedelta(days=2)
    rescheduled = client.post(
        f"/api/v1/commitments/{commitment_id}/reschedule",
        json={"deadline": new_deadline.isoformat()},
    )
    assert rescheduled.status_code == 200
    body = rescheduled.json()

    deadline_events = [h for h in body["history"] if h["event_type"] == "DEADLINE_CHANGED"]
    assert len(deadline_events) == 1
    assert deadline_events[0]["old_value"]["deadline"] is not None
    assert deadline_events[0]["new_value"]["deadline"] is not None


def test_null_deadline_is_not_overdue(client):
    resp = client.post("/api/v1/commitments", json={"title": "No deadline task", "direction": "TEAM"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["deadline"] is None
    assert body["is_overdue"] is False

    overdue_list = client.get("/api/v1/commitments", params={"overdue": "true"})
    ids = [c["id"] for c in overdue_list.json()]
    assert body["id"] not in ids


def test_create_commitment_with_invalid_person_id_returns_422(client):
    resp = client.post(
        "/api/v1/commitments",
        json={
            "title": "Task",
            "direction": "I_OWE",
            "owner_person_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert resp.status_code == 422


def test_get_missing_commitment_returns_404(client):
    resp = client.get("/api/v1/commitments/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
