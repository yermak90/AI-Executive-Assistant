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


def _create_commitment(client, **overrides):
    person_id = overrides.pop("owner_person_id", None)
    if person_id is None and overrides.get("direction", "OWED_TO_ME") != "I_OWE":
        person_id = _create_person(client)
    payload = {"title": "Task", "direction": "OWED_TO_ME", "owner_person_id": person_id}
    payload.update(overrides)
    resp = client.post("/api/v1/commitments", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["commitment"]


# --- Creation / history --------------------------------------------------


def test_create_commitment_generates_created_history(client):
    body = _create_commitment(client, title="Получить стоимость ворот")
    assert body["status"] == "ACTIVE"
    assert len(body["history"]) == 1
    assert body["history"][0]["event_type"] == "CREATED"


def test_owed_to_me_requires_owner(client):
    resp = client.post("/api/v1/commitments", json={"title": "Task", "direction": "OWED_TO_ME"})
    assert resp.status_code == 422


def test_team_requires_owner(client):
    resp = client.post("/api/v1/commitments", json={"title": "Task", "direction": "TEAM"})
    assert resp.status_code == 422


def test_i_owe_rejects_owner_person(client):
    person_id = _create_person(client)
    resp = client.post(
        "/api/v1/commitments",
        json={"title": "Task", "direction": "I_OWE", "owner_person_id": person_id},
    )
    assert resp.status_code == 422


def test_i_owe_without_owner_succeeds(client):
    resp = client.post("/api/v1/commitments", json={"title": "Отправить КП", "direction": "I_OWE"})
    assert resp.status_code == 201
    assert resp.json()["commitment"]["person"] is None


# --- Buckets (FR-005): every ACTIVE commitment exactly one bucket --------


def test_bucket_no_deadline(client):
    body = _create_commitment(client, deadline=None)
    assert body["bucket"] == "no_deadline"
    assert body["is_overdue"] is False


def test_bucket_overdue(client):
    past = (tz_now() - timedelta(hours=2)).isoformat()
    body = _create_commitment(client, deadline=past)
    assert body["bucket"] == "overdue"
    assert body["is_overdue"] is True


def test_bucket_today(client):
    deadline = tz_now().replace(hour=23, minute=0, second=0, microsecond=0)
    if deadline < tz_now():
        deadline = tz_now() + timedelta(hours=1)
    body = _create_commitment(client, deadline=deadline.isoformat())
    assert body["bucket"] == "today"


def test_bucket_tomorrow(client):
    deadline = (tz_now() + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    body = _create_commitment(client, deadline=deadline.isoformat())
    assert body["bucket"] == "tomorrow"


def test_bucket_later(client):
    deadline = tz_now() + timedelta(days=10)
    body = _create_commitment(client, deadline=deadline.isoformat())
    assert body["bucket"] == "later"


def test_every_active_commitment_appears_in_exactly_one_bucket_filter(client):
    ids = {
        "overdue": _create_commitment(client, deadline=(tz_now() - timedelta(hours=1)).isoformat())["id"],
        "today": _create_commitment(
            client, deadline=(tz_now() + timedelta(hours=1)).isoformat()
        )["id"],
        "tomorrow": _create_commitment(
            client, deadline=(tz_now() + timedelta(days=1, hours=1)).isoformat()
        )["id"],
        "later": _create_commitment(client, deadline=(tz_now() + timedelta(days=10)).isoformat())["id"],
        "no_deadline": _create_commitment(client, deadline=None)["id"],
    }

    seen = {}
    for bucket in ids:
        resp = client.get("/api/v1/commitments", params={"bucket": bucket})
        assert resp.status_code == 200
        returned_ids = [c["id"] for c in resp.json()]
        for cid in returned_ids:
            seen[cid] = seen.get(cid, 0) + 1

    for label, cid in ids.items():
        assert seen.get(cid) == 1, f"{label} commitment appeared in {seen.get(cid, 0)} bucket(s), expected exactly 1"


# --- State machine (FR-009) ----------------------------------------------


def test_complete_commitment(client):
    body = _create_commitment(client)
    resp = client.post(f"/api/v1/commitments/{body['id']}/complete")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "COMPLETED"
    assert data["completed_at"] is not None
    assert any(h["event_type"] == "COMPLETED" for h in data["history"])


def test_cannot_complete_twice(client):
    body = _create_commitment(client)
    client.post(f"/api/v1/commitments/{body['id']}/complete")
    resp = client.post(f"/api/v1/commitments/{body['id']}/complete")
    assert resp.status_code == 409


def test_cannot_cancel_after_complete(client):
    body = _create_commitment(client)
    client.post(f"/api/v1/commitments/{body['id']}/complete")
    resp = client.post(f"/api/v1/commitments/{body['id']}/cancel")
    assert resp.status_code == 409


def test_cannot_complete_after_cancel(client):
    body = _create_commitment(client)
    client.post(f"/api/v1/commitments/{body['id']}/cancel")
    resp = client.post(f"/api/v1/commitments/{body['id']}/complete")
    assert resp.status_code == 409


def test_cannot_cancel_twice(client):
    body = _create_commitment(client)
    client.post(f"/api/v1/commitments/{body['id']}/cancel")
    resp = client.post(f"/api/v1/commitments/{body['id']}/cancel")
    assert resp.status_code == 409


def test_cannot_reschedule_completed_commitment(client):
    body = _create_commitment(client)
    client.post(f"/api/v1/commitments/{body['id']}/complete")
    resp = client.post(
        f"/api/v1/commitments/{body['id']}/reschedule", json={"deadline": tz_now().isoformat()}
    )
    assert resp.status_code == 409


def test_cannot_edit_completed_commitment(client):
    body = _create_commitment(client)
    client.post(f"/api/v1/commitments/{body['id']}/complete")
    resp = client.patch(f"/api/v1/commitments/{body['id']}", json={"title": "New title"})
    assert resp.status_code == 409


def test_completed_removed_from_active_and_appears_in_archive(client):
    body = _create_commitment(client)
    client.post(f"/api/v1/commitments/{body['id']}/complete")

    active = client.get("/api/v1/commitments", params={"status": "ACTIVE"})
    assert body["id"] not in [c["id"] for c in active.json()]

    archived = client.get("/api/v1/commitments", params={"archive": "true"})
    archived_ids = [c["id"] for c in archived.json()]
    assert body["id"] in archived_ids


def test_cancelled_appears_in_archive(client):
    body = _create_commitment(client)
    client.post(f"/api/v1/commitments/{body['id']}/cancel")

    archived = client.get("/api/v1/commitments", params={"archive": "true"})
    archived_ids = [c["id"] for c in archived.json()]
    assert body["id"] in archived_ids


# --- PATCH validation (P0-04) ---------------------------------------------


def test_patch_title_null_returns_422(client):
    body = _create_commitment(client)
    resp = client.patch(f"/api/v1/commitments/{body['id']}", json={"title": None})
    assert resp.status_code == 422


def test_patch_direction_null_returns_422(client):
    body = _create_commitment(client)
    resp = client.patch(f"/api/v1/commitments/{body['id']}", json={"direction": None})
    assert resp.status_code == 422


def test_create_with_invalid_person_id_returns_422(client):
    resp = client.post(
        "/api/v1/commitments",
        json={
            "title": "Task",
            "direction": "I_OWE",
            "counterparty_person_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert resp.status_code == 422


def test_create_with_invalid_project_id_returns_422(client):
    person_id = _create_person(client)
    resp = client.post(
        "/api/v1/commitments",
        json={
            "title": "Task",
            "direction": "OWED_TO_ME",
            "owner_person_id": person_id,
            "project_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert resp.status_code == 422


def test_get_missing_commitment_returns_404(client):
    resp = client.get("/api/v1/commitments/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# --- Detailed history (FR-004 / FR-013) -----------------------------------


def test_reschedule_preserves_old_and_new_deadline_in_history(client):
    old_deadline = tz_now().replace(hour=10, minute=0, second=0, microsecond=0)
    body = _create_commitment(client, deadline=old_deadline.isoformat())

    new_deadline = tz_now() + timedelta(days=2)
    resp = client.post(
        f"/api/v1/commitments/{body['id']}/reschedule", json={"deadline": new_deadline.isoformat()}
    )
    assert resp.status_code == 200
    events = [h for h in resp.json()["commitment"]["history"] if h["event_type"] == "DEADLINE_CHANGED"]
    assert len(events) == 1
    assert events[0]["old_value"]["deadline"] is not None
    assert events[0]["new_value"]["deadline"] is not None


def test_update_title_records_old_and_new_value(client):
    body = _create_commitment(client, title="Old title")
    resp = client.patch(f"/api/v1/commitments/{body['id']}", json={"title": "New title"})
    assert resp.status_code == 200
    updated_events = [h for h in resp.json()["history"] if h["event_type"] == "UPDATED"]
    assert len(updated_events) == 1
    assert updated_events[0]["old_value"]["title"] == "Old title"
    assert updated_events[0]["new_value"]["title"] == "New title"


def test_update_owner_records_resolved_names_not_raw_ids(client):
    """P1-9: history must be human-readable — a person/project change should
    read as a name, not a bare UUID the mobile app would have to resolve
    itself (or worse, just display as-is)."""
    old_owner_id = _create_person(client, name="Аян")
    new_owner_id = _create_person(client, name="Руслан")
    body = _create_commitment(client, owner_person_id=old_owner_id)

    resp = client.patch(f"/api/v1/commitments/{body['id']}", json={"owner_person_id": new_owner_id})
    assert resp.status_code == 200, resp.text
    updated_events = [h for h in resp.json()["history"] if h["event_type"] == "UPDATED"]
    assert len(updated_events) == 1
    assert updated_events[0]["old_value"]["owner_person_id"] == "Аян"
    assert updated_events[0]["new_value"]["owner_person_id"] == "Руслан"


def test_update_with_no_actual_change_creates_no_history(client):
    body = _create_commitment(client, title="Same title")
    initial_history_len = len(body["history"])
    resp = client.patch(f"/api/v1/commitments/{body['id']}", json={"title": "Same title"})
    assert resp.status_code == 200
    assert len(resp.json()["history"]) == initial_history_len


def test_bucket_boundary_just_before_and_after_midnight(client):
    """FR-005 boundary case: a deadline one minute before local midnight is
    TODAY; one minute after midnight it is TOMORROW. This exercises the
    local-calendar-date comparison rather than a naive 24h window."""
    today_end = tz_now().replace(hour=23, minute=59, second=0, microsecond=0)
    if today_end < tz_now():
        today_end = tz_now() + timedelta(minutes=1)
    just_before_midnight = _create_commitment(client, deadline=today_end.isoformat())
    assert just_before_midnight["bucket"] in ("today", "overdue")

    tomorrow_start = (tz_now() + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
    just_after_midnight = _create_commitment(client, deadline=tomorrow_start.isoformat())
    assert just_after_midnight["bucket"] == "tomorrow"


def test_null_deadline_is_not_overdue(client):
    body = _create_commitment(client, deadline=None)
    assert body["deadline"] is None
    assert body["is_overdue"] is False

    overdue_list = client.get("/api/v1/commitments", params={"bucket": "overdue"})
    assert body["id"] not in [c["id"] for c in overdue_list.json()]


# --- P0-3: direction/ownership invariants enforced on PATCH ---------------


def test_patch_direction_to_i_owe_clears_stale_owner(client):
    """Changing direction to I_OWE without touching owner_person_id must
    clear the now-incompatible hidden field rather than leave it dangling."""
    body = _create_commitment(client)  # OWED_TO_ME with an owner
    assert body["person"] is not None

    resp = client.patch(f"/api/v1/commitments/{body['id']}", json={"direction": "I_OWE"})
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["direction"] == "I_OWE"
    assert updated["person"] is None


def test_patch_direction_to_i_owe_with_explicit_owner_rejected(client):
    body = _create_commitment(client)
    resp = client.patch(
        f"/api/v1/commitments/{body['id']}",
        json={"direction": "I_OWE", "owner_person_id": body["person"]["id"]},
    )
    assert resp.status_code == 422


def test_patch_direction_to_owed_to_me_without_owner_rejected(client):
    body = _create_commitment(client, direction="I_OWE")
    resp = client.patch(f"/api/v1/commitments/{body['id']}", json={"direction": "OWED_TO_ME"})
    assert resp.status_code == 422


def test_patch_direction_to_team_with_existing_owner_succeeds(client):
    body = _create_commitment(client)  # already has an owner
    resp = client.patch(f"/api/v1/commitments/{body['id']}", json={"direction": "TEAM"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["direction"] == "TEAM"
    assert resp.json()["person"] is not None


def test_patch_clearing_owner_on_owed_to_me_rejected(client):
    body = _create_commitment(client)
    resp = client.patch(f"/api/v1/commitments/{body['id']}", json={"owner_person_id": None})
    assert resp.status_code == 422


def test_patch_direction_to_team_without_owner_and_none_existing_rejected(client):
    body = _create_commitment(client, direction="I_OWE")
    resp = client.patch(f"/api/v1/commitments/{body['id']}", json={"direction": "TEAM"})
    assert resp.status_code == 422
