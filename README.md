# AI Executive Assistant — Sprint 1

A commitment control system for entrepreneurs and managers: track what others
owe you, what you owe others, what your team is responsible for — and get a
managerial checkpoint *before* a deadline is missed, not just a report after
it's blown.

Sprint 1 delivers the manual, AI-free foundation described in the PRD (v2.0):
people, projects, commitments with a real state machine, all five time
buckets (Overdue/Today/Tomorrow/Later/No deadline), an archive, detailed
change history, and managerial checkpoints with rule-based planning and risk
assessment. No audio, no LLM, no integrations — those are Sprint 2+.

## Repository layout

```text
backend/                FastAPI + PostgreSQL API
mobile/                 Expo (React Native + TypeScript + Expo Router) app
.github/workflows/      CI (backend tests + migrations, mobile build validation)
```

## Prerequisites

- Python 3.12+
- Node.js 18+ and npm
- PostgreSQL 16 (via Docker Compose, or a local install)

## Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example .env             # adjust DATABASE_URL / APP_TIMEZONE if needed

# Start PostgreSQL (pick one):
docker compose up -d             # option A: Dockerized Postgres (also creates
                                  # the isolated test DB automatically)
# option B: use an already-running local PostgreSQL and point DATABASE_URL at it;
# then also run: createdb ai_executive_assistant_test

alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload
```

The API is now available at `http://localhost:8000`, with interactive docs at
`http://localhost:8000/docs`.

### Windows (PowerShell) equivalents

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
docker compose up -d
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload
```

### Running backend tests

```bash
cd backend
source .venv/bin/activate
python -m pytest
```

Tests run against `TEST_DATABASE_URL` (see `.env.example` / `tests/conftest.py`),
an isolated database that is dropped and recreated on every test — it is
never the same database as `DATABASE_URL`, so running tests never touches
your dev data. `docker compose up -d` creates it automatically via
`scripts/init-test-db.sql`; without Docker, create it once with
`createdb ai_executive_assistant_test`.

### Migrations

```bash
alembic upgrade head       # apply
alembic downgrade base     # roll back everything
alembic upgrade head       # re-apply — should be clean both ways
```

All enum-like columns (direction, status, checkpoint status/assessment/source,
history event type) are stored as `VARCHAR` + `CHECK` constraint rather than
native PostgreSQL `ENUM` types. This is a deliberate choice: native PG enums
require `ALTER TYPE ... ADD VALUE` to extend and can't be cleanly reversed by
`DROP TYPE` once other objects reference them, which made `alembic downgrade`
fail on the original Sprint 1 schema. The portable-enum approach keeps
upgrade/downgrade/upgrade cycles simple with no orphaned types, at the cost of
losing DB-level enum introspection (validation still happens in the ORM layer
and via the CHECK constraint).

## Mobile setup

```bash
cd mobile
npm install    # or: npm ci
npx expo start
```

Then press `i` for iOS simulator, `a` for Android emulator, or scan the QR
code with Expo Go on a physical device.

A `.npmrc` with `legacy-peer-deps=true` is committed in `mobile/`. This is
required because `expo-router` pulls in `@expo/ui`'s web tab-bar variant,
which transitively depends on `@radix-ui/*` packages with a strict
`react-dom` peer requirement that a native-only app never installs. Without
this setting `npm ci` fails on a fresh clone even though `npm install` alone
appears to work (it just downgrades the conflict to a warning) — see
"Known limitations" below for the diagnosis. This is a normal, well-known fix
for this cause, not a workaround-of-last-resort.

### Configuring the API base URL

The mobile app talks to the backend at `http://localhost:8000/api/v1` by
default on iOS/web, and `http://10.0.2.2:8000/api/v1` on the Android
emulator (Android's alias for the host machine's `localhost`). Override this
with the `EXPO_PUBLIC_API_URL` environment variable when needed:

- **iOS simulator**: default (`http://localhost:8000/api/v1`) works as-is.
- **Android emulator**: default (`http://10.0.2.2:8000/api/v1`) works as-is.
- **Physical device**: the device cannot reach your computer's `localhost`.
  Find your computer's LAN IP (e.g. `192.168.1.42`) and run:

  ```bash
  EXPO_PUBLIC_API_URL=http://192.168.1.42:8000/api/v1 npx expo start
  ```

  Make sure the phone and computer are on the same network, and that the
  backend is bound to `0.0.0.0` (e.g. `uvicorn app.main:app --host 0.0.0.0`).

## Visual / UI testing

There is no device farm or CI-attached emulator in this project, so UI
changes are verified with a fast, repeatable, headless-browser flow rather
than only by reading code:

```bash
cd mobile
npm install --no-save react-dom react-native-web @expo/metro-runtime
npx expo start --web --port 8081
# then, from any Node script or Playwright test:
#   await page.goto("http://localhost:8081/<route>")
#   await page.screenshot(...)
```

`expo-router` screens render through `react-native-web` pixel-for-pixel close
to the native layout (same components, same StyleSheet), so this catches
layout bugs, wrong data bindings, wrong colors/badges, and broken navigation
long before a real device build. It's intentionally **not** committed as a
permanent dependency (`--no-save`) or a package.json script, since the app's
actual target is native-only and `react-dom`/`react-native-web` have no
business being a tracked dependency of a mobile-only app — pull them in only
for the duration of a visual QA pass, the same way you'd temporarily attach a
debugger.

**Known gap**: `@react-native-community/datetimepicker` has no web
implementation. Tapping the date/time button in this web preview does not
open a picker (it degrades silently — no crash, but no dialog either), and
`npx expo export --platform web` fails outright with a network error inside
this sandbox's proxy, before even reaching that difference (see "Known
limitations"). Verifying the actual native date/time picker UI, real touch
gestures, and safe-area insets on a notch/status-bar still requires an
iOS/Android simulator or a physical device — this was not done in this
sandbox and remains a manual step (see Definition of Done).

## Acceptance Scenario A — Core Commitment (PRD §22)

Automated end-to-end against a running backend (`/tmp` scratch scripts run
during development, not committed — the same steps as pytest's
`test_commitments.py` + `test_checkpoints.py`, exercised through the HTTP API
instead of the service layer directly):

1. Create person "Аян", project "Детский сад".
2. Create `OWED_TO_ME` commitment "Получить стоимость ворот", deadline today
   12:00 → appears in the `today` bucket.
3. Reschedule to an arbitrary date/time → history keeps old+new deadline.
4. Reschedule to the past → appears **only** in `overdue`, not in any other
   bucket.
5. Complete → disappears from `status=ACTIVE`, appears in `archive=true`,
   history has a `COMPLETED` entry.
6. Create a no-deadline commitment → bucket `no_deadline`.
7. Create a commitment a week out → bucket `later`.

All steps pass. ✅

## Acceptance Scenario B — Managerial Checkpoint (PRD §23)

1. Create person + project, commitment "Купить материалы" with a deadline.
2. Enable preliminary control for 2 days → an `AUTO_RULE` checkpoint is
   created at `deadline - 2 days`.
3. Add a `MANUAL` checkpoint.
4. Reschedule the commitment's deadline → the `AUTO_RULE` checkpoint moves to
   keep the same 2-day gap; the `MANUAL` one is untouched.
5. Move a checkpoint's `scheduled_at` into the past → the commitment's
   `control_health` becomes `CHECK_DUE`.
6. Assess it "Есть риск" (`AT_RISK`) with a note → checkpoint becomes
   `COMPLETED`/`AT_RISK`, commitment's `control_health` becomes `AT_RISK` and
   it shows up under `control_health=AT_RISK` ("Требует внимания").
7. Complete the commitment → the still-`PENDING` `AUTO_RULE` checkpoint is
   auto-`SKIPPED`; the already-assessed one is left `COMPLETED` (not
   re-skipped).
8. Full history contains `CHECKPOINT_CREATED`, `CHECKPOINT_AUTO_RECALCULATED`,
   `CHECKPOINT_RESCHEDULED`, `CHECKPOINT_ASSESSED_AT_RISK`,
   `CHECKPOINT_SKIPPED`, `COMPLETED`.

All steps pass. ✅

## Notes and assumptions

- **Timezone**: business rules (buckets, overdue, control health) are
  evaluated in the `APP_TIMEZONE` configured on the backend (default
  `Asia/Almaty`), never in UTC, and never re-derived on the mobile client —
  the client only reads the backend-computed `bucket` / `is_overdue` /
  `control_health` fields.
- **Portable enums**: see "Migrations" above — a deliberate departure from
  native PostgreSQL enum types to keep `alembic downgrade` clean.
- **`I_OWE` ownership**: per PRD §10.4, `I_OWE` commitments always have
  `owner_person_id = null` (the current user, implicitly) and may name a
  `counterparty_person_id` instead. `OWED_TO_ME` and `TEAM` require an owner.
  This is enforced server-side (422 otherwise), not just suggested by the UI.
- **Checkpoint gap-preservation on reschedule (FR-020)**: rather than
  re-deriving each `AUTO_RULE` checkpoint from the default planning table
  again (which could silently change how many checkpoints exist), the
  service stores each checkpoint's original gap to the old deadline and
  reapplies that same gap to the new deadline. This is simpler, keeps
  checkpoint identity/count stable across a reschedule, and matches the PRD's
  worked example exactly (a "2 days before" checkpoint stays "2 days before").
- **Default rule-planning boundaries (FR-016)**: the PRD's ranges ("2–3
  days", "4–7 days", ...) don't specify whether boundaries are inclusive.
  This implementation uses continuous, non-overlapping cutoffs: `<24h` → 2h
  lead; `<=3d` → 1d; `<=7d` → 2d; `<=14d` → 3d; `>14d` → two checkpoints
  (midpoint between creation and deadline, and deadline−3d).
- **Checkpoint deletion has no history event**: PRD §11 (FR-013) enumerates
  history event types and does not include one for deleting a checkpoint
  (only `CHECKPOINT_CREATED/UPDATED/RESCHEDULED/COMPLETED/SKIPPED/ASSESSED_*
  /AUTO_RECALCULATED`). Deleting a still-`PENDING`, never-actioned checkpoint
  is treated as a true removal (matching "удалить pending checkpoint" being
  offered as a distinct action from "skip") and does not appear in history.
- **`source_type`/`source_text`**: reserved for Sprint 2's audio → STT → LLM
  pipeline (`AI_SUGGESTED` checkpoint source, `MEETING`/`VOICE_NOTE`/etc.
  commitment source types included in the enum but unused). No AI or audio
  code exists in Sprint 1.
- **Seed is a guarded reset**: `python -m scripts.seed` refuses to run (exit
  code 1) if the database already has commitments, to avoid silently wiping
  real data (PRD §17). Pass `--reset` to force it.

## Known limitations (read before treating this as fully verified)

- **`npx expo export --platform web` cannot be run inside this sandbox** —
  it fails on an unrelated proxy-blocked network call before bundling even
  starts. Native platform exports (`--platform ios`, `--platform android`)
  and `npx expo start --web` (dev server, not export) both work fine and were
  used for verification instead; this is a sandbox networking artifact, not
  a project defect, but it hasn't been independently re-confirmed outside
  this environment.
- **`npx expo-doctor` reports 19/21 passing here**, with the 2 failures being
  network calls to `docs.expo.dev` / the React Native Directory API that this
  sandbox's egress proxy blocks (confirmed by the "Host not in allowlist"
  text leaking into a JSON parse error). These should pass on a machine with
  normal internet access; not independently confirmed.
- **No physical device or simulator was used.** All UI verification was via
  Expo web + a headless browser (see "Visual / UI testing"). The native
  date/time picker's actual on-device UI, gesture handling, and safe-area
  behavior on a real notch/status bar are unverified.
- **GitHub Actions has not been observed running.** The workflow in
  `.github/workflows/ci.yml` mirrors every command verified locally
  (`alembic upgrade/downgrade/upgrade`, `pytest`, `npm ci`, `npm run
  typecheck`, `expo-doctor`, `expo export --platform android`), but whether
  it is actually green on GitHub's runners should be checked after pushing,
  not assumed from local success alone.
