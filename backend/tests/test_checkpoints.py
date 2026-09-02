from datetime import timedelta

from app.core.timezone import now as tz_now


def _create_person(client, name="Аян"):
    resp = client.post("/api/v1/people", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_commitment(client, **overrides):
    person_id = overrides.pop("owner_person_id", None)
    if person_id is None and overrides.get("direction", "OWED_TO_ME") != "I_OWE":
        person_id = _create_person(client)
    payload = {"title": "Купить материалы", "direction": "OWED_TO_ME", "owner_person_id": person_id}
    payload.update(overrides)
    resp = client.post("/api/v1/commitments", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- Manual checkpoint CRUD (FR-014) ---------------------------------------


def test_create_manual_checkpoint(client):
    deadline = tz_now() + timedelta(days=5)
    commitment = _create_commitment(client, deadline=deadline.isoformat())

    scheduled_at = tz_now() + timedelta(days=2)
    resp = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Проверить заказ материалов", "scheduled_at": scheduled_at.isoformat()},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "PENDING"
    assert body["source_type"] == "MANUAL"

    history = client.get(f"/api/v1/commitments/{commitment['id']}").json()["history"]
    assert any(h["event_type"] == "CHECKPOINT_CREATED" for h in history)


def test_manual_checkpoint_before_created_at_rejected(client):
    deadline = tz_now() + timedelta(days=5)
    commitment = _create_commitment(client, deadline=deadline.isoformat())

    resp = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Too early", "scheduled_at": (tz_now() - timedelta(days=1)).isoformat()},
    )
    assert resp.status_code == 422


def test_manual_checkpoint_after_deadline_rejected(client):
    deadline = tz_now() + timedelta(days=5)
    commitment = _create_commitment(client, deadline=deadline.isoformat())

    resp = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Too late", "scheduled_at": (deadline + timedelta(days=1)).isoformat()},
    )
    assert resp.status_code == 422


def test_manual_checkpoint_allowed_without_deadline(client):
    commitment = _create_commitment(client, deadline=None)
    scheduled_at = tz_now() + timedelta(days=1)
    resp = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Check anyway", "scheduled_at": scheduled_at.isoformat()},
    )
    assert resp.status_code == 201


def test_duplicate_scheduled_at_rejected(client):
    deadline = tz_now() + timedelta(days=5)
    commitment = _create_commitment(client, deadline=deadline.isoformat())
    scheduled_at = (tz_now() + timedelta(days=2)).isoformat()

    first = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "First", "scheduled_at": scheduled_at},
    )
    assert first.status_code == 201

    second = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Duplicate", "scheduled_at": scheduled_at},
    )
    assert second.status_code == 422


def test_no_checkpoint_for_final_state_commitment(client):
    commitment = _create_commitment(client, deadline=(tz_now() + timedelta(days=5)).isoformat())
    client.post(f"/api/v1/commitments/{commitment['id']}/complete")

    resp = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Too late", "scheduled_at": tz_now().isoformat()},
    )
    assert resp.status_code == 409


def test_delete_pending_checkpoint(client):
    deadline = tz_now() + timedelta(days=5)
    commitment = _create_commitment(client, deadline=deadline.isoformat())
    created = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Remove me", "scheduled_at": (tz_now() + timedelta(days=1)).isoformat()},
    ).json()

    resp = client.delete(f"/api/v1/checkpoints/{created['id']}")
    assert resp.status_code == 204

    remaining = client.get(f"/api/v1/commitments/{commitment['id']}/checkpoints").json()
    assert created["id"] not in [c["id"] for c in remaining]


# --- Auto-rule generation (FR-015 / FR-016) --------------------------------


def test_explicit_lead_time_generates_checkpoint_at_deadline_minus_days(client):
    deadline = tz_now() + timedelta(days=5)
    commitment = _create_commitment(
        client,
        deadline=deadline.isoformat(),
        enable_control=True,
        lead_time_days=2,
    )
    checkpoints = commitment["checkpoints"]
    assert len(checkpoints) == 1
    scheduled_at = checkpoints[0]["scheduled_at"]
    # deadline - 2 days, same time of day
    from datetime import datetime

    assert datetime.fromisoformat(scheduled_at) == deadline - timedelta(days=2)
    assert checkpoints[0]["source_type"] == "AUTO_RULE"


def test_default_rule_short_task_under_24h(client):
    deadline = tz_now() + timedelta(hours=10)
    commitment = _create_commitment(client, deadline=deadline.isoformat(), enable_control=True)
    assert len(commitment["checkpoints"]) == 1


def test_default_rule_long_task_creates_two_checkpoints(client):
    deadline = tz_now() + timedelta(days=30)
    commitment = _create_commitment(client, deadline=deadline.isoformat(), enable_control=True)
    assert len(commitment["checkpoints"]) == 2


def test_no_auto_checkpoint_without_deadline(client):
    commitment = _create_commitment(client, deadline=None)
    resp = client.post(f"/api/v1/commitments/{commitment['id']}/checkpoints/generate", json={})
    assert resp.status_code == 422


# --- Assessment + control health (FR-018 / FR-019) -------------------------


def test_assess_at_risk_sets_checkpoint_completed_and_commitment_at_risk(client):
    deadline = tz_now() + timedelta(days=5)
    commitment = _create_commitment(client, deadline=deadline.isoformat())
    checkpoint = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Check", "scheduled_at": (tz_now() + timedelta(hours=1)).isoformat()},
    ).json()

    resp = client.post(
        f"/api/v1/checkpoints/{checkpoint['id']}/assess",
        json={"assessment": "AT_RISK", "assessment_note": "Поставщик не подтвердил наличие"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["assessment"] == "AT_RISK"

    detail = client.get(f"/api/v1/commitments/{commitment['id']}").json()
    assert detail["control_health"] == "AT_RISK"
    assert any(h["event_type"] == "CHECKPOINT_ASSESSED_AT_RISK" for h in detail["history"])

    attention = client.get("/api/v1/commitments", params={"control_health": "AT_RISK"}).json()
    assert commitment["id"] in [c["id"] for c in attention]


def test_check_due_when_pending_checkpoint_in_past(client):
    deadline = tz_now() + timedelta(days=5)
    commitment = _create_commitment(client, deadline=deadline.isoformat())
    # Scheduled for "now" (a few ms after the commitment's created_at, which
    # satisfies the >= created_at rule); by the time we check control_health
    # below, real time has moved past it, so it reads as due.
    created = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Due now", "scheduled_at": tz_now().isoformat()},
    )
    assert created.status_code == 201, created.text
    detail = client.get(f"/api/v1/commitments/{commitment['id']}").json()
    assert detail["control_health"] == "CHECK_DUE"


def test_cannot_assess_twice(client):
    deadline = tz_now() + timedelta(days=5)
    commitment = _create_commitment(client, deadline=deadline.isoformat())
    checkpoint = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Check", "scheduled_at": (tz_now() + timedelta(hours=1)).isoformat()},
    ).json()
    client.post(f"/api/v1/checkpoints/{checkpoint['id']}/assess", json={"assessment": "ON_TRACK"})
    resp = client.post(f"/api/v1/checkpoints/{checkpoint['id']}/assess", json={"assessment": "AT_RISK"})
    assert resp.status_code == 409


# --- Reschedule recalculation (FR-020) --------------------------------------


def test_reschedule_recalculates_auto_but_not_manual(client):
    deadline = tz_now().replace(hour=18, minute=0, second=0, microsecond=0) + timedelta(days=5)
    commitment = _create_commitment(
        client, deadline=deadline.isoformat(), enable_control=True, lead_time_days=2
    )
    auto_checkpoint = commitment["checkpoints"][0]

    manual_scheduled_at = tz_now() + timedelta(days=1)
    manual_checkpoint = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Manual check", "scheduled_at": manual_scheduled_at.isoformat()},
    ).json()

    new_deadline = deadline + timedelta(days=7)
    resp = client.post(
        f"/api/v1/commitments/{commitment['id']}/reschedule", json={"deadline": new_deadline.isoformat()}
    )
    assert resp.status_code == 200
    body = resp.json()

    from datetime import datetime

    updated_auto = next(cp for cp in body["checkpoints"] if cp["id"] == auto_checkpoint["id"])
    updated_manual = next(cp for cp in body["checkpoints"] if cp["id"] == manual_checkpoint["id"])

    assert datetime.fromisoformat(updated_auto["scheduled_at"]) == new_deadline - timedelta(days=2)
    assert datetime.fromisoformat(updated_manual["scheduled_at"]) == manual_scheduled_at
    assert any(h["event_type"] == "CHECKPOINT_AUTO_RECALCULATED" for h in body["history"])


# --- Completion/cancellation skip pending checkpoints (FR-010/FR-011) ------


def test_complete_skips_pending_checkpoints(client):
    deadline = tz_now() + timedelta(days=5)
    commitment = _create_commitment(client, deadline=deadline.isoformat())
    checkpoint = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Check", "scheduled_at": (tz_now() + timedelta(hours=1)).isoformat()},
    ).json()

    resp = client.post(f"/api/v1/commitments/{commitment['id']}/complete")
    assert resp.status_code == 200
    body = resp.json()
    updated = next(cp for cp in body["checkpoints"] if cp["id"] == checkpoint["id"])
    assert updated["status"] == "SKIPPED"
    assert any(h["event_type"] == "CHECKPOINT_SKIPPED" for h in body["history"])


def test_cancel_skips_pending_checkpoints(client):
    deadline = tz_now() + timedelta(days=5)
    commitment = _create_commitment(client, deadline=deadline.isoformat())
    checkpoint = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Check", "scheduled_at": (tz_now() + timedelta(hours=1)).isoformat()},
    ).json()

    resp = client.post(f"/api/v1/commitments/{commitment['id']}/cancel")
    assert resp.status_code == 200
    body = resp.json()
    updated = next(cp for cp in body["checkpoints"] if cp["id"] == checkpoint["id"])
    assert updated["status"] == "SKIPPED"


def test_already_assessed_checkpoint_not_reskipped_by_completion(client):
    deadline = tz_now() + timedelta(days=5)
    commitment = _create_commitment(client, deadline=deadline.isoformat())
    checkpoint = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Check", "scheduled_at": (tz_now() + timedelta(hours=1)).isoformat()},
    ).json()
    client.post(f"/api/v1/checkpoints/{checkpoint['id']}/assess", json={"assessment": "ON_TRACK"})

    resp = client.post(f"/api/v1/commitments/{commitment['id']}/complete")
    body = resp.json()
    updated = next(cp for cp in body["checkpoints"] if cp["id"] == checkpoint["id"])
    assert updated["status"] == "COMPLETED"
    assert updated["assessment"] == "ON_TRACK"
