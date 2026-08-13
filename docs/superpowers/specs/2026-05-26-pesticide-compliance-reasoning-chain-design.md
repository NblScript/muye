# Pesticide Compliance Reasoning Chain Design

## Goal

Build the next competition-facing technical innovation around a pesticide safety and compliance reasoning chain.

Muye already has an end-to-end pipeline: pest detection, RAG-enhanced AI decision making, compliance checks, drone execution, reporting, and dashboard visualization. The next step is to make the safety layer explicit, explainable, and visible enough for judges to understand that the system does not let an LLM directly trigger pesticide spraying.

The core claim:

> Muye generates AI pest-control recommendations, then audits them through a pesticide safety and compliance reasoning chain before drone execution. The audit checks evidence sources, crop applicability, target pest applicability, toxicity/safety, and weather constraints. Its result directly controls whether the drone can proceed automatically, must wait for human confirmation, or is blocked.

## Non-Goals

- Do not replace the existing RAG, decision, or drone pipeline.
- Do not build a full legal-regulatory expert system in this phase.
- Do not add complex animation or presentation-only effects before the backend result is structured and testable.
- Do not depend on external network access for the competition demo path.

## User-Facing Innovation

The feature should be presented as:

**Pesticide Safety Compliance Reasoning Chain**

It sits between AI decision generation and drone execution:

```text
Pest detection
  -> RAG retrieval
  -> AI pest-control recommendation
  -> Compliance reasoning chain
  -> passed / warning / blocked
  -> auto execution / human confirmation / execution blocked
```

This turns the existing safety logic into a visible engineering mechanism with four judge-facing qualities:

- Recommendation is evidence-backed.
- Risk is checked by explicit rules.
- Execution permission is controlled by risk level.
- The whole process is traceable in the dashboard and report.

## Backend Design

Extend the existing compliance layer in `modules/decision/compliance.py` instead of creating a separate subsystem.

The compliance layer should return a structured reasoning result with these fields:

```python
{
    "status": "passed | warning | blocked",
    "score": 100,
    "summary": "Human-readable audit conclusion derived from checks",
    "checks": [
        {
            "rule": "crop_match",
            "name": "Crop applicability",
            "status": "passed | warning | blocked",
            "message": "The pesticide applies to the current crop.",
            "evidence": [
                {
                    "source": "pesticide_catalog",
                    "title": "Catalog entry name",
                    "matched_fields": ["target_crops"]
                }
            ]
        }
    ],
    "execution_policy": {
        "takeoff_mode": "auto | manual | blocked",
        "reason": "warning requires human confirmation"
    },
    "alternatives": []
}
```

MVP compatibility decisions:

- Keep the existing `score` field as the canonical compliance safety score. It remains a 0-100 score where 100 is safest. Do not add a separate top-level `risk_score` in MVP; the dashboard can render risk as `100 - score` when it needs risk-first wording.
- Add `summary` as a deterministic rule-derived sentence based on `status`, `blocking_reasons`, `warnings`, and failed checks. Do not call an LLM to generate compliance summaries in MVP.
- Keep `alternatives` in the response shape, but return an empty list in MVP. Alternative pesticide recommendation requires candidate ranking and filtering, so it is Phase 2.
- Keep current check fields `rule`, `status`, and `message`. The frontend may display `rule` as the check id and `message` as the reason. Do not require a separate `id` or `reason` field in MVP.

The first implementation should keep five fixed checks:

1. **Source credibility** (`source_match`)
   - Whether the recommended pesticide appears in RAG results or structured catalog data.
2. **Crop applicability** (`crop_match`)
   - Whether the pesticide is suitable for the current crop.
3. **Target pest applicability** (`pest_match`)
   - Whether the pesticide covers the detected pest or normalized pest synonym.
4. **Safety level** (`toxicity_risk`)
   - Whether the pesticide is high toxicity, restricted, or unsuitable for the demo scenario.
5. **Weather constraint** (`weather_risk`)
   - Whether wind, rain, and temperature permit spraying.

These names intentionally match the existing `modules/decision/compliance.py` rule names.

Evidence mapping:

- RAG candidates currently expose `content`, `score`, and `metadata`.
- `evidence.source` should come from `metadata.source` when present, otherwise from the collection type such as `pesticides`, `historical_cases`, or `knowledge`.
- `evidence.title` should prefer `metadata.product_name`, then `metadata.active_ingredient`, then a concise first-line or truncated value from `content`.
- `evidence.score` may carry the candidate retrieval score.
- `evidence.matched_fields` should be derived from the fields actually used by the check:
  - `source_match`: `product_name`, `active_ingredient`, or `content`
  - `crop_match`: `target_crops` or content field `适用作物`
  - `pest_match`: `target_pests` or content field `防治对象`
  - `toxicity_risk`: `toxicity` or content field `毒性`
  - `weather_risk`: weather keys such as `wind_speed`, `humidity`, and `temperature`

Status policy:

- `passed`: drone may continue according to configured takeoff mode.
- `warning`: drone must enter manual confirmation, even if configured as auto.
- `blocked`: drone must not start PX4 or execute spraying.

The main pipeline in `app/main.py` should consume only the normalized compliance result and its `execution_policy`. It should not duplicate compliance rule logic.

## Frontend Design

Upgrade the existing compliance audit area in `DecisionExplainPanel` into a dashboard section named:

**农药安全合规推理链**

In MVP, this should not be a separate competing panel unless layout extraction is needed. It should replace the current lightweight compliance area inside `DecisionExplainPanel`, while keeping its position after the AI decision explanation and before the drone execution controls. This position makes the safety audit visible as the gate between recommendation and action.

The panel should include four areas:

1. **Audit summary**
   - Overall state: `passed`, `warning`, or `blocked`.
   - Safety score from backend `score`, such as `68/100`; if the UI uses risk wording, render it as `100 - score`.
   - Execution policy: auto execution, human confirmation, or execution blocked.

2. **Five-check chain**
   - Source credibility.
   - Crop applicability.
   - Target pest applicability.
   - Safety level.
   - Weather constraint.

   Each check should show state, short reason, and whether it changed execution permission.

3. **Evidence sources**
   - Show concise source names and matched fields.
   - Avoid long document excerpts.
   - Make clear which part came from pesticide catalog, historical case, or agricultural knowledge.

4. **Execution impact**
   - `passed`: enters spraying workflow.
   - `warning`: waits for human confirmation.
   - `blocked`: stops task and records risk.

The panel should not describe how to use the UI. It should present the system state directly.

## Report Design

The generated competition report should include a compliance audit section:

- Overall compliance status.
- Safety score from backend `score`, with optional risk wording derived as `100 - score`.
- The five check results.
- Key evidence sources.
- Final execution policy.

This lets the same technical innovation appear in the live dashboard and exported report.

## Demo Scenarios

Prepare three deterministic demo scenarios:

1. **Safe pass**
   - Crop, pest, pesticide, and weather all match.
   - Expected status: `passed`.
   - Expected execution: continue to drone workflow.

2. **Risk confirmation**
   - Recommendation is usable but has weak evidence or weather risk.
   - Expected status: `warning`.
   - Expected execution: force manual confirmation.

3. **Execution blocked**
   - Pesticide does not match crop/pest, or safety risk is too high.
   - Expected status: `blocked`.
   - Expected execution: do not start PX4 and record risk.

These scenarios should be reproducible through the existing demo script mechanism.

## Testing Strategy

Backend tests:

- Compliance unit tests for all five checks.
- Status aggregation tests for `passed`, `warning`, and `blocked`.
- Summary derivation tests proving `summary` is generated from rules and not from an LLM.
- Evidence mapping tests for RAG candidate `metadata`, `content`, and `score`.
- Pipeline tests proving:
  - `passed` can continue.
  - `warning` forces manual confirmation.
  - `blocked` does not start PX4 or spraying. These tests should mock `DroneController` or the resolved drone backend; they should not require a live PX4 integration environment.

Frontend tests:

- Panel renders all five checks.
- Panel renders evidence sources.
- Panel renders execution policy for all three statuses.
- Existing `DecisionExplainPanel` compliance rendering is upgraded rather than duplicated.

Script/demo tests:

- Demo scenario variables reach backend processing.
- All three scenarios are reproducible offline.

Report tests:

- Generated report includes compliance summary, score, checks, evidence, and execution policy.

## Acceptance Criteria

- Compliance result includes `status`, `score`, `summary`, `checks`, and `execution_policy`; every check can carry `checks[*].evidence`.
- MVP returns `alternatives: []`; populated alternatives are Phase 2.
- Every `warning` result forces manual confirmation.
- Every `blocked` result prevents PX4 startup and spraying execution.
- Dashboard shows the five-check reasoning chain.
- Report includes the compliance audit summary.
- Three demo scenarios reproduce `passed`, `warning`, and `blocked`.
- Offline demo mode can show the complete reasoning chain without external network dependency.

## Competition Explanation

Use this concise explanation in the defense:

> Muye is not just a YOLO plus RAG demo. It adds an explainable pesticide safety compliance reasoning chain between AI recommendation and drone execution. The system checks evidence, crop applicability, target pest applicability, toxicity risk, and weather constraints. The audit result directly controls execution permission, so the system can recommend, audit, block unsafe action, and preserve a traceable record.
