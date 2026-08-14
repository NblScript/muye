# Backend Reliability Slices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve backend reliability by splitting liveness from readiness and moving takeoff confirmation state into SQLite-backed service logic.

**Architecture:** Keep HTTP routes stable while introducing focused service functions. `/live` is a cheap process liveness endpoint; `/health` remains readiness diagnostics. Takeoff confirmation keeps the existing file/event compatibility path but records the canonical pending/confirmed/expired action in SQLite.

**Tech Stack:** FastAPI, SQLite, pytest, existing `SqliteStore` mixin structure.

---

### Task 1: Liveness Endpoint

**Files:**
- Modify: `app/routes/health.py`
- Test: `tests/test_main.py`
- Docs: `docs/references/api.md`, `RELIABILITY.md`

- [x] Add `api_live()` returning `{"status": "ok"}` without dependency checks.
- [x] Register `/live` and `/api/live`.
- [x] Add a pytest asserting `api_live()` returns immediately with `status == "ok"`.

### Task 2: SQLite Pending Action Store

**Files:**
- Modify: `modules/infra/sqlite_store/base.py`
- Modify: `modules/infra/sqlite_store/task.py`
- Test: `tests/test_takeoff_confirmation_service.py`

- [x] Add `pending_actions` table with `request_id`, `action_type`, `status`, `created_at`, `confirmed_at`, `expires_at`.
- [x] Add methods to create, read, confirm, expire, and clear pending actions.
- [x] Add pytest coverage for pending → confirmed and pending → expired.

### Task 3: Takeoff Confirmation Service

**Files:**
- Create: `app/services/takeoff_confirmation_service.py`
- Modify: `app/deps.py`
- Modify: `app/routes/drone.py`
- Test: `tests/test_main.py`, `tests/test_takeoff_confirmation_service.py`

- [x] Create service functions that wrap SQLite pending actions and preserve file/event compatibility.
- [x] Make `deps.set_pending_takeoff_request`, `deps.mark_takeoff_confirmed`, `deps.wait_for_takeoff_confirmation`, and `deps.clear_takeoff_confirmation_state` call the service.
- [x] Keep `POST /drone/confirm-takeoff` behavior compatible with existing tests.

### Task 4: Verification and Docs

**Files:**
- Modify: `AGENTS.md`, `RELIABILITY.md`, `docs/references/api.md`, `ARCHITECTURE.md`

- [x] Document `/live` versus `/health`.
- [x] Document SQLite-backed takeoff confirmation.
- [x] Run `pytest` target tests, `scripts/check.sh`, and `scripts/verify_docs.py`.

### Task 5: PX4 Process Helper Extraction

**Files:**
- Create: `app/services/px4_process_service.py`
- Modify: `app/routes/drone.py`
- Modify: `app/routes/health.py`
- Test: `tests/test_px4_process_service.py`, `tests/test_main.py`
- Docs: `AGENTS.md`, `ARCHITECTURE.md`, `RELIABILITY.md`

- [x] Move PID file, port probing, PX4 process detection, log wrapper, and process kill helpers into `px4_process_service.py`.
- [x] Keep `app.routes.drone` compatibility wrappers so existing route tests and monkeypatches continue to work.
- [x] Make `/health` PX4 readiness use `px4_process_service` instead of importing route internals.
- [x] Add pytest coverage for service PID file and Gazebo resource path helpers.
