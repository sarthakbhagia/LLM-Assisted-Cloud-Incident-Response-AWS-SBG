# End-to-End Architecture Guide

This is the practical map of the project: what happens from a fault to a verified outcome, which files take part, and where to change the system safely.

## 1. What the system is

The project is an event-driven AWS incident-response system for three fault classes:

| Fault class | Detection source | Primary evidence |
| --- | --- | --- |
| `resource_exhaustion` | CloudWatch Lambda alarm | Lambda metrics and CloudWatch Logs Insights |
| `misconfiguration` | AWS Config or GuardDuty | Config compliance/history and GuardDuty finding |
| `service_cascade` | CloudWatch composite alarm | Metrics/logs for Services A, B, C and X-Ray traces |

The end-to-end lifecycle is:

```text
Demo application or injected fault
  -> CloudWatch / AWS Config / GuardDuty
  -> EventBridge (or local direct invocation)
  -> Collector
  -> S3 raw evidence + DynamoDB incident record
  -> Diagnosis with Bedrock and a matching runbook
  -> Slack/dashboard approval
  -> Remediation
  -> Verification
  -> DynamoDB record updated for the dashboard and evaluation
```

The deployed infrastructure is declared in [infra/template.yaml](../infra/template.yaml). The local runtime uses the same handler modules through [local_backend.py](../local_backend.py).

## 2. Deployed components

| Component | AWS responsibility | Main implementation |
| --- | --- | --- |
| Demo services | A request chain: Service A -> B -> C | [backend/service_a/app.py](../backend/service_a/app.py), [backend/service_b/app.py](../backend/service_b/app.py), [backend/service_c/app.py](../backend/service_c/app.py) |
| Detection | Alarms, Config rules, GuardDuty and EventBridge routing | [infra/template.yaml](../infra/template.yaml) |
| Collector | Normalizes detection events, fetches evidence, creates incidents | [backend/collector/collector_lambda.py](../backend/collector/collector_lambda.py) |
| Evidence store | Immutable-ish raw incident JSON and runbooks | S3 `IncidentDataLake`; access is configured in [infra/template.yaml](../infra/template.yaml) |
| Incident store | Lifecycle/status record for each incident | DynamoDB `IncidentsTable`; initial record is written by the collector |
| Diagnosis | Uses raw evidence plus runbook context to produce structured RCA/remediation suggestions | [backend/diagnosis/diagnosis_lambda.py](../backend/diagnosis/diagnosis_lambda.py), [backend/diagnosis/prompts.py](../backend/diagnosis/prompts.py), [backend/diagnosis/runbook_loader.py](../backend/diagnosis/runbook_loader.py) |
| Notification/approval | Posts to Slack and validates signed human decisions | [backend/reporting/notify_lambda.py](../backend/reporting/notify_lambda.py), [backend/approval/approval_handler.py](../backend/approval/approval_handler.py) |
| Remediation | Executes the selected approved action | [backend/remediation/remediation_lambda.py](../backend/remediation/remediation_lambda.py), [backend/remediation/actions.py](../backend/remediation/actions.py) |
| Verification | Re-checks the original signal after remediation | [backend/verification/verification_lambda.py](../backend/verification/verification_lambda.py) |
| Dashboard API | Read-only incident/evidence/runbook/analytics endpoints | [backend/dashboard_api/dashboard_api_lambda.py](../backend/dashboard_api/dashboard_api_lambda.py) |
| Dashboard actions | Dashboard approval, rejection, re-diagnosis, trace, and service endpoints | [backend/dashboard_api/dashboard_actions_lambda.py](../backend/dashboard_api/dashboard_actions_lambda.py) |
| React dashboard | Operator UI and replay UI | [frontend/src](../frontend/src) |
| Demo-control API | Injects demo faults and supports demo approval | [backend/demo_control/demo_control_lambda.py](../backend/demo_control/demo_control_lambda.py), [infra/demo-control-template.yaml](../infra/demo-control-template.yaml) |

## 3. Runtime flow, in order

### Step 1: Create a signal

There are two ways an incident starts.

**Normal AWS flow**

1. A request reaches Service A at `/start`.
2. Service A calls Service B, which calls Service C.
3. CloudWatch alarms, AWS Config rules, or GuardDuty emit a detection event.
4. EventBridge rules in [infra/template.yaml](../infra/template.yaml) target `CollectorFunction`.

**Demo/local flow**

1. The user selects a fault in the dashboard's demo panel.
2. [backend/demo_control/demo_control_lambda.py](../backend/demo_control/demo_control_lambda.py) injects the fault.
3. In deployed AWS mode, the alarm/EventBridge route is authoritative. In local mode, `LOCAL::collector` is invoked directly to avoid a second EventBridge-created incident.
4. [local_backend.py](../local_backend.py) implements `LocalLambdaRouter`, which intercepts `LOCAL::*` Lambda invokes and executes the in-process handler.

The standalone scripts in [fault_injection](../fault_injection) are an alternative command-line entry point for fault injection.

### Step 2: Collect evidence and create the incident

[backend/collector/collector_lambda.py](../backend/collector/collector_lambda.py) is the first lifecycle Lambda.

1. `lambda_handler` assigns an incident ID and calculates the collection window.
2. `_parse_event` converts CloudWatch, Config, GuardDuty, and manual demo events into one internal shape.
3. `_collect_evidence` dispatches by `fault_class`:
   - `_collect_resource_exhaustion`: resolves the affected Lambda, reads alarm details, runs Logs Insights, and gets Duration/Errors/Throttles/Invocations.
   - `_collect_misconfiguration`: retrieves AWS Config compliance/history and, where available, the GuardDuty finding.
   - `_collect_service_cascade`: resolves Services A/B/C, reads their logs and metrics, and requests X-Ray summaries/service graph data.
4. The complete raw bundle is written to `incidents/<incident_id>/raw_data.json` in S3.
5. `_write_incident_record` creates a DynamoDB record containing detection context, the S3 key, initial diagnosis/remediation/verification state.
6. The collector asynchronously invokes diagnosis when `DIAGNOSIS_FUNCTION_NAME` is configured.

The raw S3 JSON is the source of truth for evidence. DynamoDB is the lifecycle/index record used by APIs and workflow stages.

### Step 3: Diagnose using evidence and a runbook

[backend/diagnosis/diagnosis_lambda.py](../backend/diagnosis/diagnosis_lambda.py) loads the DynamoDB record and raw S3 evidence.

1. [backend/diagnosis/runbook_loader.py](../backend/diagnosis/runbook_loader.py) selects the matching Markdown runbook in [knowledge_base](../knowledge_base).
2. [backend/diagnosis/prompts.py](../backend/diagnosis/prompts.py) builds the structured diagnosis prompt.
3. The Lambda invokes the configured Amazon Bedrock model/fallback chain.
4. The response is validated and written into the incident's `diagnosis` object in DynamoDB.
5. The notification Lambda is invoked when configured.

The diagnosis output includes root cause, confidence, reasoning, affected resources, suggested action, and recommended solutions. It must remain evidence-grounded; it is not an approval to mutate infrastructure.

### Step 4: Notify and obtain human approval

[backend/reporting/notify_lambda.py](../backend/reporting/notify_lambda.py) formats the incident and diagnosis for Slack. It reads the webhook URL and approval secret from SSM SecureString parameters.

The Slack approval link reaches [backend/approval/approval_handler.py](../backend/approval/approval_handler.py) at `/approval`. The handler verifies the HMAC-backed decision, prevents invalid lifecycle transitions, updates DynamoDB, and invokes remediation only for an approved incident.

The React dashboard can use the dashboard action endpoints instead:

```text
POST /api/incidents/{id}/approve
POST /api/incidents/{id}/reject
POST /api/incidents/{id}/diagnose
```

Those routes are implemented by [backend/dashboard_api/dashboard_actions_lambda.py](../backend/dashboard_api/dashboard_actions_lambda.py).

### Step 5: Remediate and verify

[backend/remediation/remediation_lambda.py](../backend/remediation/remediation_lambda.py) reads the approved incident and delegates action-specific AWS calls to [backend/remediation/actions.py](../backend/remediation/actions.py). Supported actions include scaling a Lambda, restarting a service, locking an S3 bucket, tightening an IAM policy, and manual-review outcomes.

It writes the execution result back to DynamoDB and invokes [backend/verification/verification_lambda.py](../backend/verification/verification_lambda.py).

Verification re-checks the original signal rather than assuming a successful API call means the incident is resolved:

- Lambda/alarm incidents: re-check relevant CloudWatch metrics or alarm state.
- Service-cascade incidents: re-check the composite/component alarm state and affected service telemetry.
- Misconfiguration incidents: re-check Config compliance for the flagged resource.

It records `resolved`, `not_resolved`, or `inconclusive`, plus the evidence for that decision, in the incident record.

## 4. Dashboard data flow

[frontend/src/config/api.js](../frontend/src/config/api.js) is the single HTTP client. It appends `/api/...` paths to `VITE_API_BASE_URL`; production values must end at `/Prod`, not `/Prod/api`.

| UI area | Main files | Data source |
| --- | --- | --- |
| App routing/layout | [frontend/src/App.jsx](../frontend/src/App.jsx), [frontend/src/components/Layout.jsx](../frontend/src/components/Layout.jsx) | React Router |
| Overview and incident feed | [frontend/src/pages/Overview.jsx](../frontend/src/pages/Overview.jsx), [frontend/src/components/IncidentFeed.jsx](../frontend/src/components/IncidentFeed.jsx) | `GET /api/incidents` |
| Incident detail/evidence | [frontend/src/pages/IncidentDetail.jsx](../frontend/src/pages/IncidentDetail.jsx) | `GET /api/incidents/{id}` and `/evidence` |
| Replay mode | [frontend/src/pages/ReplayMode.jsx](../frontend/src/pages/ReplayMode.jsx) | Same incident/evidence endpoints; shares `EvidenceExplorer` |
| Demo controls | [frontend/src/components/DemoControls.jsx](../frontend/src/components/DemoControls.jsx) | `POST /demo/inject` and incident polling |
| Analytics | [frontend/src/pages/Analytics.jsx](../frontend/src/pages/Analytics.jsx) | `GET /api/analytics` |
| Service map/health/runbooks | [frontend/src/pages/ServiceMap.jsx](../frontend/src/pages/ServiceMap.jsx), [frontend/src/pages/SystemHealth.jsx](../frontend/src/pages/SystemHealth.jsx), [frontend/src/pages/Runbooks.jsx](../frontend/src/pages/Runbooks.jsx) | `/api/services`, `/api/health`, `/api/runbooks` |

[backend/dashboard_api/dashboard_api_lambda.py](../backend/dashboard_api/dashboard_api_lambda.py) is intentionally read-only: it reads DynamoDB for incident summaries and S3 for raw evidence. Its IAM role in [infra/template.yaml](../infra/template.yaml) explicitly denies DynamoDB and S3 writes.

### Evidence shape consumed by the UI

The evidence endpoint returns an envelope whose raw data is nested at `data.evidence.evidence`:

```json
{
  "incident_id": "...",
  "fault_class": "service_cascade",
  "s3_key": "incidents/.../raw_data.json",
  "evidence": {
    "detection_event": { "...": "..." },
    "evidence": {
      "metrics": { "service_a_duration": [{ "timestamp": "...", "value": 42 }] },
      "logs_insights": { "rows": [] }
    }
  }
}
```

`EvidenceExplorer` in [frontend/src/pages/IncidentDetail.jsx](../frontend/src/pages/IncidentDetail.jsx) renders this inner bundle. Metric values must be a flat object of array-valued series; Service Cascade therefore uses namespaced keys such as `service_a_duration`.

Misconfiguration is intentionally a Config-evidence flow, not a Lambda telemetry flow. Its useful tab is **Config**; it normally has no CloudWatch Logs or Metrics tab.

## 5. Local development topology

Run [scripts/start_local.sh](../scripts/start_local.sh) to start the local backend, then run the Vite app from `frontend/`.

| Local endpoint | Provided by | Purpose |
| --- | --- | --- |
| `http://localhost:3001` | [local_backend.py](../local_backend.py) | Main dashboard API and local action routes |
| `http://localhost:3002` | [local_backend.py](../local_backend.py) | Demo-control API |
| Vite dev server | [frontend/vite.config.js](../frontend/vite.config.js) | React UI; proxies local `/api` requests when no API base URL is configured |

The local process imports Lambda modules at startup. Restart it after changing backend Lambda code. It still uses configured AWS credentials and real AWS data services unless a local router handles the Lambda invocation; it is not a complete AWS emulator.

## 6. Where to change common behavior

| Change needed | Start here | Also inspect |
| --- | --- | --- |
| Add a fault class | collector parser/dispatcher | EventBridge/alarms in `infra/template.yaml`, runbook, diagnosis prompt rules, remediation/verification, frontend labels/tabs, tests |
| Change telemetry/evidence | `backend/collector/collector_lambda.py` | `IncidentDetail.jsx` and `ReplayMode.jsx` consumer shape |
| Change diagnosis schema or prompting | `backend/diagnosis/prompts.py` | `diagnosis_lambda.py`, UI fields, tests |
| Add remediation action | `backend/remediation/actions.py` | validation/allow-lists, IAM permissions, verification mapping, runbooks |
| Add dashboard endpoint | dashboard API/action Lambda | SAM API event, `frontend/src/config/api.js`, UI caller |
| Change demo behavior | `backend/demo_control/demo_control_lambda.py` | `local_backend.py`, demo UI polling, and deployed demo-control template |
| Change infrastructure permission/route | `infra/template.yaml` | matching handler configuration and deployment script |

## 7. Tests, evaluation, and operations

| Area | Location | When to use it |
| --- | --- | --- |
| Python unit/integration tests | [tests](../tests) | Validate handlers and cross-Lambda behavior |
| React tests | [frontend/src](../frontend/src) (`*.test.*`) | Validate rendering, API-state handling, and page behavior |
| Evaluation harness | [evaluation/run_evaluation.py](../evaluation/run_evaluation.py), [evaluation/metrics.py](../evaluation/metrics.py) | Measure diagnosis/recovery quality and timing |
| Fault-injection scripts | [fault_injection](../fault_injection) | Reproduce the three incident classes outside the UI |
| Deploy/local scripts | [scripts](../scripts) | Deploy SAM stacks, run/stop local services, sync runbooks |

Before treating a workflow change as complete, test the full contract: emitted event -> collector raw S3 evidence -> DynamoDB lifecycle record -> API response -> UI renderer -> approval/remediation/verification transition.

## 8. Important operational constraints

- The dashboard read API must stay read-only. Put all mutations in approval/remediation or the separate dashboard actions API.
- Do not put `/api` in `VITE_API_BASE_URL`; the client already adds that path.
- S3 evidence written for an existing incident is historical. Code changes affect new incidents only unless evidence is deliberately regenerated.
- Synthetic demo evidence must be clearly marked (`demo_synthetic`) and guarded by `injected_by == "demo_mode"`; it must never replace real incident evidence.
- Local direct invocation avoids duplicate local records, but it does not create genuine CloudWatch logs, metrics, or X-Ray traffic. Demo-only fallback evidence is required when the UI needs illustrative telemetry.

## 9. Keeping this document current

Update this file whenever a fault class, Lambda, API route, incident state, evidence schema, or deployment boundary changes. The best review question is: “Can a new contributor follow this document from an emitted event to the exact JSON rendered in the dashboard?”
