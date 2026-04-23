# API Reference

## Health
- GET /health - System health check

## Workflow
- GET /workflow/state - Current workflow state
- GET /workflow/history - Workflow history

## Dashboard
- GET /dashboard/context - Dashboard context data

## Demo
- POST /demo/upload-image - Upload demo image
- POST /demo/reset-events - Reset demo events

## Tasks
- GET /tasks/{request_id} - Get task by ID
- GET /tasks/{request_id}/original - Get original image
- GET /tasks/{request_id}/annotated - Get annotated image

## Simulation
- GET /sim/map-state - Get simulation map state
- WebSocket /sim/ws - Real-time map updates
