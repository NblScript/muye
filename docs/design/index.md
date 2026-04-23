# Design Documentation

## Core Beliefs

1. Agent-first development: Code should be readable by both humans and AI agents
2. Domain-driven structure: Modules organized by business domain (decision, drone, detection, infra)
3. Test coverage as contract: 77+ tests enforce behavior contracts
4. SQLite for simplicity: Single-file database for portability and reliability
5. Progressive disclosure: Documentation starts simple, details on demand

## Architecture Layers

app/          - FastAPI application layer (routes, services, main entry)
modules/      - Core business logic by domain
  decision/   - AI decision and RAG knowledge enhancement
  drone/      - Drone control, mission planning, PX4 simulation
  detection/  - YOLO image processing, data collection
  infra/      - Shared infrastructure (events, storage, weather)
models/       - Data models and schemas
config/       - Runtime configuration files

## Key Design Decisions

- See docs/reference/data-model.md for SQLite schema
- See docs/plans/ for implementation roadmaps
- See docs/operations/runbooks/ for operational procedures
