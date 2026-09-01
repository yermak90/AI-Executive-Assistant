# AI Executive Assistant — Sprint 1

A commitment control system for entrepreneurs and managers: track what others
owe you, what you owe others, and what your team is responsible for.

Sprint 1 delivers the manual, AI-free foundation described in the PRD:
people, projects, commitments, Today/Overdue control, rescheduling,
completion, and a full change history. No audio, no LLM, no integrations —
those are Sprint 2+.

## Repository layout

```text
backend/   FastAPI + PostgreSQL API
mobile/    Expo (React Native + TypeScript + Expo Router) app
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
docker compose up -d             # option A: Dockerized Postgres
# option B: use an already-running local PostgreSQL and point DATABASE_URL at it

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

Tests run against a separate `ai_executive_assistant_test` database (see
`tests/conftest.py`); create it once with `createdb ai_executive_assistant_test`
if you are not using Docker Compose.

## Mobile setup

```bash
cd mobile
npm install
npx expo start
```

Then press `i` for iOS simulator, `a` for Android emulator, or scan the QR
code with Expo Go on a physical device.

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

## Acceptance scenario (manual QA)

From a fresh database (or after re-running the seed script):

1. Create project "Детский сад".
2. Create person "Аян".
3. Create commitment "Получить стоимость ворот", person Аян, project
   Детский сад, direction "Мне должны", deadline today 12:00.
4. Open the Today screen — the commitment appears under today.
5. Change the deadline to tomorrow — it leaves Today, and the commitment's
   history shows a `DEADLINE_CHANGED` entry with both the old and new value.
6. Change the deadline to a past time — the commitment now shows as overdue.
7. Mark it completed — status becomes `COMPLETED`, it disappears from active
   control lists, and history records a `COMPLETED` entry.

## Notes and assumptions

- **Timezone**: business rules (Today / overdue) are evaluated in the
  `APP_TIMEZONE` configured on the backend (default `Asia/Almaty`), never in
  UTC. The mobile app never independently decides whether something is
  overdue — it always reads `is_overdue` from the API.
- **`due=tomorrow` filter**: the PRD's API spec lists `due=today`; a
  `due=tomorrow` variant was added using the same filter model so the
  Control screen's "Завтра" section stays backend-computed rather than
  guessed on the client, consistent with the "backend owns business logic"
  principle.
- **`I_OWE` without a person**: per the PRD, commitments the current user
  owes (`I_OWE`) may have `owner_person_id = null` instead of a fake "self"
  person record. The mobile UI shows "Вы" in that case.
- **Deadline picker**: Sprint 1 uses a lightweight custom picker (quick-day
  chips + an hour/minute input) instead of a native date-picker dependency,
  in keeping with the "avoid adding large libraries unless justified"
  guidance. It can be swapped for a native picker later without touching the
  API layer.
- **Source type**: commitments carry a `source_type` column (default
  `MANUAL`) reserved for Sprint 2's audio → STT → LLM pipeline. No source
  integration is implemented in Sprint 1.
