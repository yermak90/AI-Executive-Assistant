# AI Executive Assistant — Product Requirements Document (v2.0)

## 1. Problem

Entrepreneurs and managers lose track of commitments — what others owe them,
what they owe others, what their team is responsible for — and typically
find out something slipped only *after* the deadline has passed. The product
is a commitment control system that surfaces a managerial checkpoint
*before* a deadline is missed, not a report after the fact.

## 2. Sprint scope

- **Sprint 1 (this repository, current state): manual, AI-free foundation.**
  A person can enter commitments, checkpoints, and reschedules by hand; the
  system enforces the business rules (state machine, direction/ownership
  invariants, buckets, checkpoint scheduling, control health) and keeps a
  full audit trail. No audio capture, no speech-to-text, no LLM, no external
  integrations exist anywhere in this codebase.
- **Sprint 2 (not started): AI-assisted capture.** Audio/voice-note capture,
  transcription, and an LLM that drafts commitments and checkpoint
  title/question/reason text from natural language. Sprint 1 leaves explicit
  seams for this (see §9) but ships zero AI code, so Sprint 2 can be added
  without touching Sprint 1's invariants.

Sprint 1 must not be treated as done until every requirement below is met
*and* verified against a running backend + mobile app (see §12, Definition
of Done) — not just implemented and unit-tested.

## 3. Core entities

| Entity | Purpose |
| --- | --- |
| `Person` | Someone who can be an owner or a counterparty on a commitment. |
| `Project` | Optional grouping for commitments; can be activated/deactivated. |
| `Commitment` | The thing being tracked: title, description, direction, owner, counterparty, project, deadline, status. |
| `CommitmentCheckpoint` | A scheduled managerial check-in on a commitment: title, question, reason, scheduled time, assessment. |
| `CommitmentHistory` | An immutable audit log entry recording what changed on a commitment or its checkpoints, and when. |

## 4. Direction and ownership (§10.4)

Every commitment has a `direction`:

- **`OWED_TO_ME`** — someone else owes the current user. Requires
  `owner_person_id` (who owes it).
- **`I_OWE`** — the current user owes someone else. `owner_person_id` must
  be `null` (the owner is implicitly "me"); a `counterparty_person_id` may
  optionally name who it's owed to.
- **`TEAM`** — a team member is responsible. Requires `owner_person_id`.

**Invariant, enforced server-side on both create and update (422 on
violation, never just a UI suggestion):** on `PATCH`, the server merges the
existing row with the incoming partial update *before* validating — so
changing only `direction` re-validates the pre-existing `owner_person_id`
against the *new* direction, and changing only `owner_person_id` re-validates
against the *existing* direction. When a `PATCH` changes `direction` to
`I_OWE`, any stale `owner_person_id` already on the row is cleared
automatically rather than left as an orphaned, now-invalid value.

## 5. Time buckets (FR-005)

Every `ACTIVE` commitment belongs to exactly one bucket, computed
server-side in `APP_TIMEZONE` (never UTC, never re-derived on the client):

- `overdue` — deadline in the past.
- `today` — deadline is today (local date).
- `tomorrow` — deadline is tomorrow (local date).
- `later` — deadline is more than one day out.
- `no_deadline` — no deadline set.

Completed/cancelled commitments have no bucket; they live in the archive
(§7) instead.

## 6. Commitment fields and lifecycle

- **Fields**: `title` (required), `description` (optional free text),
  `direction`, `owner_person_id`, `counterparty_person_id`, `project_id`,
  `deadline` (optional datetime), `source_text` (reserved for Sprint 2),
  `lead_time_days` (drives auto-checkpoint planning, §8).
- **Deadline picker (FR-008)**: quick options ("Today" / "Tomorrow" / "In 3
  days") are always computed from the *current* local date and time, never
  from whatever value the picker previously held — picking "Tomorrow" twice
  in a row must not compound into "the day after tomorrow." Editing or
  rescheduling a commitment must preserve its existing deadline as the
  starting point rather than resetting to a default. Arbitrary date/time
  selection (not just the quick options) must remain available.
- **State machine (FR-009)**: a commitment is `ACTIVE`, `COMPLETED`, or
  `CANCELLED`. Both `COMPLETED` and `CANCELLED` are terminal: no further
  edits, reschedules, completes, or cancels are accepted from either state
  (409 Conflict). Completing or cancelling a commitment auto-`SKIP`s any
  still-`PENDING` checkpoint (FR-010/FR-011) without touching checkpoints
  already `COMPLETED`/`SKIPPED`.

## 7. Archive (FR-012)

Completed and cancelled commitments are never deleted. They are excluded
from the default (`archive=false`) list and bucket views, and retrievable
via `archive=true`, preserving their full history and checkpoints.

## 8. Managerial checkpoints

### 8.1 Manual checkpoints (FR-014)

A checkpoint can be created, edited, or deleted by hand at any time while
the commitment is `ACTIVE`, with `title` (required), `question` (optional),
`reason` (optional), and `scheduled_at` (required). A still-`PENDING`
checkpoint can be deleted outright (no history event — deleting an
un-actioned checkpoint is a true removal, not an audited state
transition) or explicitly skipped (which *is* an audited transition,
`CHECKPOINT_SKIPPED`).

### 8.2 Opt-in control at creation (FR-015)

When creating a commitment with a deadline, control can be enabled
(`enable_control=true`) with a lead time in days (presets: 1/2/3/7, plus a
free-form custom value) and an optional control question/reason. This
generates one `AUTO_RULE` checkpoint at `deadline - lead_time_days`.

### 8.3 Default rule-based planning (FR-016)

When no explicit lead time is given, the system falls back to a planning
table based on time remaining until the deadline:

| Time remaining | Checkpoint(s) |
| --- | --- |
| < 24h | deadline − 2h |
| ≤ 3 days | deadline − 1 day |
| ≤ 7 days | deadline − 2 days |
| ≤ 14 days | deadline − 3 days |
| > 14 days | midpoint(created_at, deadline), and deadline − 3 days |

**Immediate attention (P0, no signal loss allowed):** if a rule-computed (or
explicitly requested) checkpoint time is earlier than the commitment's
`created_at`, it is *not* silently dropped — it is clamped to `created_at`
and the checkpoint is still created, and the generation/reschedule response
carries `immediate_attention_required: true`. Clients must surface this
explicitly (e.g. a blocking alert), not just leave it to be discovered by
the checkpoint's own health status.

### 8.4 Editable control settings (FR-017)

`lead_time_days` (and the associated control question/reason) can be
changed after creation, from the commitment detail screen, and re-triggers
checkpoint generation with the new value. This must go through the same
`immediate_attention_required` contract as initial creation.

### 8.5 Assessment and skip (FR-018)

A `PENDING` checkpoint can be:

- **Assessed** as `ON_TRACK`, `AT_RISK`, or `BLOCKED` with an optional note
  — transitions it to `COMPLETED` and records the assessment.
- **Skipped** — transitions it to `SKIPPED` without an assessment.

An already-`COMPLETED` or `SKIPPED` checkpoint cannot be re-assessed (409).

### 8.6 Control health (FR-019)

`control_health` on a commitment is derived, in priority order:

1. `BLOCKED` — latest assessed checkpoint was `BLOCKED`.
2. `AT_RISK` — latest assessed checkpoint was `AT_RISK`.
3. `CHECK_DUE` — a `PENDING` checkpoint's `scheduled_at` has passed.
4. `ON_TRACK` — otherwise (including all non-`ACTIVE` commitments).

`needs_attention` (used to group "Требует внимания" in the UI) is true for
`BLOCKED`, `AT_RISK`, and `CHECK_DUE`.

### 8.7 Reschedule recalculation (FR-020)

Rescheduling a commitment's deadline:

- Shifts every still-`PENDING` `AUTO_RULE` checkpoint by the *same gap* it
  held relative to the old deadline (a "2 days before" checkpoint stays "2
  days before" the new deadline), recorded as `CHECKPOINT_AUTO_RECALCULATED`.
- Never moves `MANUAL` checkpoints.
- If shifting an `AUTO_RULE` checkpoint would land it before `created_at`,
  it is clamped to `created_at` and `immediate_attention_required: true` is
  returned — the same rule as §8.3, applied here too.
- If a `MANUAL` checkpoint now falls *after* the new (earlier) deadline, it
  is left untouched but reported back as
  `manual_checkpoints_after_deadline` so the caller can warn the user
  instead of leaving a silent inconsistency.

## 9. Sprint-2 compatibility seams (no AI in Sprint 1)

- `source_type` / `source_text` on `Commitment`, and the `AI_SUGGESTED`
  checkpoint source, exist in the schema for Sprint 2's audio → STT → LLM
  pipeline but are unused by any Sprint 1 code path.
- `CheckpointSuggestionProvider` (`backend/app/services/checkpoint_suggestions.py`)
  is a `Protocol` for drafting checkpoint title/question/reason text.
  Sprint 1 wires in only `RuleBasedCheckpointSuggestionProvider` — a fixed
  template, no network calls, no AI. Sprint 2 can add an LLM-backed
  implementation of the same Protocol and swap it in at the single
  assignment point in `checkpoints.py` without changing any caller.

## 10. History (FR-004 / FR-013)

Every commitment and checkpoint mutation is recorded as a
`CommitmentHistory` row with an `event_type`, `old_value`, and `new_value`
(both JSON, `null` for a pure creation snapshot). Event types:
`CREATED`, `UPDATED`, `DEADLINE_CHANGED`, `COMPLETED`, `CANCELLED`,
`CHECKPOINT_CREATED`, `CHECKPOINT_UPDATED`, `CHECKPOINT_RESCHEDULED`,
`CHECKPOINT_COMPLETED`, `CHECKPOINT_SKIPPED`,
`CHECKPOINT_ASSESSED_ON_TRACK` / `_AT_RISK` / `_BLOCKED`,
`CHECKPOINT_AUTO_RECALCULATED`.

For `title`, `direction`, `owner`, `counterparty`, `project`, `deadline`,
and checkpoint fields, `old_value`/`new_value` must resolve to
human-readable text (a person's or project's *name*, not its UUID; a
direction's display label, not its enum code) — resolved **at write time**,
so a later rename of the referenced person/project does not retroactively
change what the history says happened. A no-op update (new value equal to
old) does not produce a history entry.

## 11. Data integrity requirements

- **Migration history is linear and additive, never squashed or rewritten.**
  Every historical revision ID that has ever shipped remains a valid,
  reachable `down_revision` target. `alembic upgrade head` run against an
  existing Sprint 1 database (an old schema with real data already in it)
  must complete with all existing data intact — this is a CI-enforced
  regression test (`backend/tests/test_migrations.py`), not just a manual
  check. Resetting or dropping a database is never an acceptable fix for a
  migration defect.
- A full `alembic downgrade base` → `alembic upgrade head` cycle must be
  clean and repeatable (no orphaned enum types, no unnamed constraints that
  can't be dropped).

## 12. Definition of Done (Sprint 1)

A change is not done until all of the following pass, in order:

1. `alembic upgrade` from the last shipped revision to `head`, against a
   database that already has data — data preserved.
2. `alembic downgrade base && alembic upgrade head` on a clean database.
3. `pytest` (backend) — full suite green.
4. `npm ci` (mobile) — clean install from the committed lockfile.
5. `npm run typecheck` (mobile) — no TypeScript errors.
6. `npx expo-doctor` (mobile).
7. A native export (`npx expo export --platform android`, at minimum).
8. A manual pass on an Android emulator or a real device — automated tests
   and typechecking verify *code* correctness, not *feature* correctness;
   claiming a UI feature works requires having actually operated it.

## 13. Acceptance scenarios

See `README.md` → "Acceptance Scenario A — Core Commitment" and
"Acceptance Scenario B — Managerial Checkpoint" for the concrete,
reproducible step-by-step scripts used to validate this PRD end to end.
