# Pipeline Stage Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `app/main.py` pipeline complexity by extracting pure decision helpers for compliance policy and spray planning.

**Architecture:** Keep `MuyeApplication._process_image()` as the orchestration entry point, but move deterministic policy and planning helpers into focused `app/services/` modules. This preserves the runtime flow while making individual rules testable without booting the full application.

**Tech Stack:** Python, pytest, existing FastAPI application services.

---

### Task 1: Compliance Policy Extraction

**Files:**
- Create: `app/services/pipeline_policy_service.py`
- Modify: `app/main.py`
- Test: `tests/test_pipeline_policy_service.py`

- [x] Add `resolve_policy_takeoff_mode()` to convert compliance output into `blocked/manual/auto`.
- [x] Add `resolve_runtime_takeoff_mode()` to apply configured takeoff mode and compliance warning override.
- [x] Replace inline policy parsing in `_process_image()` with the service helpers.

### Task 2: Spray Planning Extraction

**Files:**
- Create: `app/services/pipeline_planning_service.py`
- Modify: `app/main.py`
- Test: `tests/test_pipeline_planning_service.py`

- [x] Add `detection_has_bbox()` for geometry detection.
- [x] Add `plan_spray_mission()` that chooses variable-rate planning when geofence and detection geometry are available.
- [x] Keep `_plan_spray_mission()` as a thin orchestration wrapper that logs and falls back to uniform planning.

### Task 3: Verification and Docs

**Files:**
- Modify: `AGENTS.md`
- Modify: `ARCHITECTURE.md`

- [x] Document pipeline helper services.
- [x] Run target tests and full project verification.
