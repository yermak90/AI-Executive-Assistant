from datetime import timedelta

import pytest

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
    return resp.json()["commitment"]


def _create_commitment_raw(client, **overrides):
    """Like _create_commitment but returns the full wrapper response
    (commitment + immediate_attention_required), for tests that need the
    creation-time signal itself rather than just the commitment."""
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


def test_generate_response_shape_includes_checkpoints_and_flag(client):
    deadline = tz_now() + timedelta(days=5)
    commitment = _create_commitment(client, deadline=deadline.isoformat())
    resp = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints/generate", json={"lead_time_days": 2}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "checkpoints" in body
    assert "immediate_attention_required" in body
    assert len(body["checkpoints"]) == 1
    assert body["immediate_attention_required"] is False


def test_immediate_attention_required_when_commitment_due_in_one_hour(client):
    """P0-04: a commitment due in just 1 hour falls under the default rule's
    "< 24h -> 2h lead" bucket, so the computed checkpoint time (deadline -
    2h) is already in the past. That must surface as
    immediate_attention_required=True, not get silently created and lost."""
    deadline = tz_now() + timedelta(hours=1)
    commitment = _create_commitment(client, deadline=deadline.isoformat())

    resp = client.post(f"/api/v1/commitments/{commitment['id']}/checkpoints/generate", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["immediate_attention_required"] is True
    assert len(body["checkpoints"]) == 1

    # The commitment itself must also read as needing attention right away.
    detail = client.get(f"/api/v1/commitments/{commitment['id']}").json()
    assert detail["control_health"] == "CHECK_DUE"


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
    body = resp.json()["commitment"]

    from datetime import datetime

    updated_auto = next(cp for cp in body["checkpoints"] if cp["id"] == auto_checkpoint["id"])
    updated_manual = next(cp for cp in body["checkpoints"] if cp["id"] == manual_checkpoint["id"])

    assert datetime.fromisoformat(updated_auto["scheduled_at"]) == new_deadline - timedelta(days=2)
    assert datetime.fromisoformat(updated_manual["scheduled_at"]) == manual_scheduled_at
    assert any(h["event_type"] == "CHECKPOINT_AUTO_RECALCULATED" for h in body["history"])


def test_reschedule_warns_about_manual_checkpoint_after_new_deadline(client):
    """P1-08: MANUAL checkpoints are never moved by a reschedule, so pulling
    the deadline in earlier can strand one past it — that must be surfaced,
    not left as a silent inconsistency."""
    deadline = tz_now() + timedelta(days=10)
    commitment = _create_commitment(client, deadline=deadline.isoformat())

    manual_scheduled_at = tz_now() + timedelta(days=8)
    client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Проверка перед сдачей", "scheduled_at": manual_scheduled_at.isoformat()},
    )

    new_deadline = tz_now() + timedelta(days=3)
    resp = client.post(
        f"/api/v1/commitments/{commitment['id']}/reschedule", json={"deadline": new_deadline.isoformat()}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["manual_checkpoints_after_deadline"]) == 1
    assert body["manual_checkpoints_after_deadline"][0]["title"] == "Проверка перед сдачей"


def test_reschedule_to_near_deadline_clamps_auto_checkpoint_and_flags_immediate_attention(client):
    """P1-08: shifting an AUTO_RULE checkpoint by the reschedule gap must not
    land it before the commitment's created_at — it should clamp to
    created_at and flag immediate_attention_required rather than silently
    producing a checkpoint that predates the commitment."""
    deadline = tz_now() + timedelta(days=30)
    commitment = _create_commitment(client, deadline=deadline.isoformat(), enable_control=True, lead_time_days=2)

    new_deadline = tz_now() + timedelta(hours=1)
    resp = client.post(
        f"/api/v1/commitments/{commitment['id']}/reschedule", json={"deadline": new_deadline.isoformat()}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["immediate_attention_required"] is True

    from datetime import datetime

    auto_checkpoint = body["commitment"]["checkpoints"][0]
    assert datetime.fromisoformat(auto_checkpoint["scheduled_at"]) == datetime.fromisoformat(commitment["created_at"])


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


# --- Creation-time control + immediate attention (review follow-up) --------


def test_create_with_enable_control_due_in_one_hour_returns_immediate_attention(client):
    """A commitment created with preliminary control already enabled and a
    deadline just 1 hour away falls under the default rule's "<24h -> 2h
    lead" bucket, so the checkpoint's computed time is already in the past.
    That must come back on the CREATE response itself, not only be
    discoverable later via control_health."""
    deadline = tz_now() + timedelta(hours=1)
    body = _create_commitment_raw(client, deadline=deadline.isoformat(), enable_control=True)
    assert body["immediate_attention_required"] is True
    assert len(body["commitment"]["checkpoints"]) == 1

    detail = client.get(f"/api/v1/commitments/{body['commitment']['id']}").json()
    assert detail["control_health"] == "CHECK_DUE"


def test_create_with_enable_control_far_deadline_returns_no_immediate_attention(client):
    deadline = tz_now() + timedelta(days=10)
    body = _create_commitment_raw(client, deadline=deadline.isoformat(), enable_control=True, lead_time_days=2)
    assert body["immediate_attention_required"] is False


def test_create_commitment_and_checkpoint_generation_is_transactional(client, monkeypatch):
    """If checkpoint generation blows up mid-creation, the commitment must
    not be left half-created in the database — either everything from this
    request lands, or none of it does."""
    from app.services import checkpoint_suggestions

    def _boom(self, commitment, scheduled_at, reference_time):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(checkpoint_suggestions.RuleBasedCheckpointSuggestionProvider, "suggest", _boom)

    deadline = tz_now() + timedelta(days=10)
    payload = {
        "title": "Не должно сохраниться",
        "direction": "OWED_TO_ME",
        "owner_person_id": _create_person(client, name="Даулет"),
        "deadline": deadline.isoformat(),
        "enable_control": True,
        "lead_time_days": 2,
    }
    with pytest.raises(RuntimeError):
        client.post("/api/v1/commitments", json=payload)

    listing = client.get("/api/v1/commitments").json()
    assert all(c["title"] != "Не должно сохраниться" for c in listing)


def test_generate_with_question_and_reason_overrides_applies_to_checkpoint(client):
    deadline = tz_now() + timedelta(days=10)
    commitment = _create_commitment(client, deadline=deadline.isoformat())
    resp = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints/generate",
        json={"lead_time_days": 2, "question": "Уточнили у поставщика?", "reason": "Иначе сорвём срок"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checkpoints"][0]["question"] == "Уточнили у поставщика?"
    assert body["checkpoints"][0]["reason"] == "Иначе сорвём срок"


# --- Editable control settings replace, not duplicate (P1-06) --------------


def test_regenerate_with_new_lead_time_replaces_not_duplicates(client):
    deadline = tz_now() + timedelta(days=10)
    commitment = _create_commitment(client, deadline=deadline.isoformat(), enable_control=True, lead_time_days=2)
    assert len(commitment["checkpoints"]) == 1
    original_checkpoint_id = commitment["checkpoints"][0]["id"]

    resp = client.post(f"/api/v1/commitments/{commitment['id']}/checkpoints/generate", json={"lead_time_days": 3})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert len(body["checkpoints"]) == 1
    assert body["checkpoints"][0]["id"] == original_checkpoint_id

    from datetime import datetime

    assert datetime.fromisoformat(body["checkpoints"][0]["scheduled_at"]) == deadline - timedelta(days=3)

    detail = client.get(f"/api/v1/commitments/{commitment['id']}").json()
    assert len(detail["checkpoints"]) == 1
    assert any(h["event_type"] == "CHECKPOINT_AUTO_RECALCULATED" for h in detail["history"])


def test_regenerate_does_not_touch_manual_or_completed_checkpoints(client):
    deadline = tz_now() + timedelta(days=10)
    commitment = _create_commitment(client, deadline=deadline.isoformat(), enable_control=True, lead_time_days=2)
    auto_checkpoint_id = commitment["checkpoints"][0]["id"]

    client.post(f"/api/v1/checkpoints/{auto_checkpoint_id}/assess", json={"assessment": "ON_TRACK"})
    manual = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Проверка вручную", "scheduled_at": (tz_now() + timedelta(days=1)).isoformat()},
    ).json()

    resp = client.post(f"/api/v1/commitments/{commitment['id']}/checkpoints/generate", json={"lead_time_days": 3})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # The old AUTO_RULE checkpoint is COMPLETED, not stale-PENDING, so it is
    # never a candidate for reuse — a fresh AUTO_RULE checkpoint is created.
    assert len(body["checkpoints"]) == 1
    assert body["checkpoints"][0]["id"] != auto_checkpoint_id

    detail = client.get(f"/api/v1/commitments/{commitment['id']}").json()
    by_id = {cp["id"]: cp for cp in detail["checkpoints"]}
    assert len(detail["checkpoints"]) == 3
    assert by_id[auto_checkpoint_id]["status"] == "COMPLETED"
    assert by_id[auto_checkpoint_id]["assessment"] == "ON_TRACK"
    assert by_id[manual["id"]]["status"] == "PENDING"
    assert by_id[manual["id"]]["source_type"] == "MANUAL"


def test_disable_control_skips_pending_auto_checkpoint_leaves_manual(client):
    deadline = tz_now() + timedelta(days=10)
    commitment = _create_commitment(client, deadline=deadline.isoformat(), enable_control=True, lead_time_days=2)
    auto_checkpoint_id = commitment["checkpoints"][0]["id"]
    manual = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Проверка вручную", "scheduled_at": (tz_now() + timedelta(days=1)).isoformat()},
    ).json()

    resp = client.patch(f"/api/v1/commitments/{commitment['id']}", json={"lead_time_days": None})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    by_id = {cp["id"]: cp for cp in body["checkpoints"]}
    assert body["lead_time_days"] is None
    assert by_id[auto_checkpoint_id]["status"] == "SKIPPED"
    assert by_id[manual["id"]]["status"] == "PENDING"
    assert any(h["event_type"] == "CHECKPOINT_SKIPPED" for h in body["history"])


# --- Checkpoint update history (review follow-up) ---------------------------


def test_checkpoint_update_records_real_old_and_new_values(client):
    deadline = tz_now() + timedelta(days=5)
    commitment = _create_commitment(client, deadline=deadline.isoformat())
    checkpoint = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={
            "title": "Старое название",
            "question": "Старый вопрос?",
            "reason": "Старая причина",
            "scheduled_at": (tz_now() + timedelta(days=1)).isoformat(),
        },
    ).json()

    resp = client.patch(
        f"/api/v1/checkpoints/{checkpoint['id']}",
        json={"title": "Новое название", "question": "Новый вопрос?", "reason": "Новая причина"},
    )
    assert resp.status_code == 200, resp.text

    detail = client.get(f"/api/v1/commitments/{commitment['id']}").json()
    updated_events = [h for h in detail["history"] if h["event_type"] == "CHECKPOINT_UPDATED"]
    assert len(updated_events) == 1
    assert updated_events[0]["old_value"] == {
        "title": "Старое название",
        "question": "Старый вопрос?",
        "reason": "Старая причина",
    }
    assert updated_events[0]["new_value"] == {
        "title": "Новое название",
        "question": "Новый вопрос?",
        "reason": "Новая причина",
    }


def test_checkpoint_update_records_only_the_fields_that_actually_changed(client):
    deadline = tz_now() + timedelta(days=5)
    commitment = _create_commitment(client, deadline=deadline.isoformat())
    checkpoint = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Проверка", "question": "Вопрос?", "scheduled_at": (tz_now() + timedelta(days=1)).isoformat()},
    ).json()

    resp = client.patch(
        f"/api/v1/checkpoints/{checkpoint['id']}",
        json={"title": "Проверка", "question": "Новый вопрос?"},
    )
    assert resp.status_code == 200, resp.text

    detail = client.get(f"/api/v1/commitments/{commitment['id']}").json()
    updated_events = [h for h in detail["history"] if h["event_type"] == "CHECKPOINT_UPDATED"]
    assert len(updated_events) == 1
    assert updated_events[0]["old_value"] == {"question": "Вопрос?"}
    assert updated_events[0]["new_value"] == {"question": "Новый вопрос?"}


def test_checkpoint_no_op_update_creates_no_history(client):
    deadline = tz_now() + timedelta(days=5)
    commitment = _create_commitment(client, deadline=deadline.isoformat())
    checkpoint = client.post(
        f"/api/v1/commitments/{commitment['id']}/checkpoints",
        json={"title": "Проверка", "scheduled_at": (tz_now() + timedelta(days=1)).isoformat()},
    ).json()

    resp = client.patch(f"/api/v1/checkpoints/{checkpoint['id']}", json={"title": "Проверка"})
    assert resp.status_code == 200, resp.text

    detail = client.get(f"/api/v1/commitments/{commitment['id']}").json()
    assert not any(h["event_type"] == "CHECKPOINT_UPDATED" for h in detail["history"])
