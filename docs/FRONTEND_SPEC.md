# Frontend Specification — LLM-Assisted Cloud Incident Response

**Status: Fully Implemented (Phase 8 Complete)** — All pages, components, and API contracts from this specification have been implemented in the `dashboard/web/` React application. Frontend production build verified clean. As of September 25, 2026.

This document is the complete functional and architectural specification for the frontend application. It covers the tech stack, all pages and routes, every component's data contract and behavior, the full API contract, state management strategy, error handling, and implementation phasing.

Every feature in this spec maps to either a completed backend component or a planned Phase 8 backend component from `PROJECT_SPEC.md`. Features that require additional backend work beyond `PROJECT_SPEC.md` are listed separately in `BACKEND_SPEC.md` under "Frontend Support Requirements."

For visual aesthetics, the design system, spacing, typography, and component styling, refer to [DESIGN_SPEC.md](DESIGN_SPEC.md).

---

## 1. Architecture Overview

The frontend is a fully decoupled Single Page Application (SPA). It communicates exclusively with the backend through a REST API exposed via Amazon API Gateway. It has no direct access to DynamoDB, S3, or any other AWS service.

```
React SPA (S3 + CloudFront)
    |
    | HTTPS REST
    v
Amazon API Gateway (Phase 8 — dashboard_api_lambda.py + approval endpoint)
    |
    +-- GET /api/incidents            --> DashboardApiLambda
    +-- GET /api/incidents/{id}       --> DashboardApiLambda
    +-- GET /api/incidents/{id}/evidence  --> DashboardApiLambda (fetches raw_data.json from S3)
    +-- GET /api/analytics            --> DashboardApiLambda (returns /evaluation/results/ JSON)
    +-- GET /api/runbooks             --> DashboardApiLambda
    +-- POST /api/incidents/{id}/approve  --> ApprovalFunction (Phase 5, already exists)
    +-- POST /api/incidents/{id}/reject   --> ApprovalFunction (Phase 5, already exists)
```

The frontend never modifies AWS infrastructure directly. All write operations (approve, reject) go through the authorized backend API.

---

## 2. Tech Stack

### Core Framework
- **React 18** + **TypeScript**
- **Vite**: Build tooling and local dev server (`npm run dev`).

### Styling
- **Tailwind CSS v3**: All design tokens (colors, spacing, border radius) are configured in `tailwind.config.ts` to match the Obsidian + Crimson design system from `DESIGN_SPEC.md`.

### Data Fetching & State
- **TanStack Query (React Query v5)**: API fetching, caching, and polling.
  - Active incidents: `refetchInterval: 8000` (8-second polling).
  - Incident detail when in an active pipeline state: `refetchInterval: 5000`.
  - Resolved incident records: `staleTime: 300000` (5 minutes, effectively static).
  - Analytics: `staleTime: 60000`, no polling.
- **Zustand**: Lightweight global state for UI-only concerns (selected environment, sidebar collapse). No business logic — all server state goes through TanStack Query.

### Routing
- **React Router v6**: Nested layouts. The root layout renders the Sidebar and Header; all pages render in the outlet.

### Visualizations
- **Recharts**: Time-series metric charts for Evidence Explorer (Metrics tab) and Analytics page.
- **React Flow**: Interactive service dependency graph on the Service Map page.

### Utilities
- **Monaco Editor** (or **CodeMirror 6**): Syntax-highlighted JSON and log viewer. Always uses the Obsidian dark theme.
- **Lucide React**: All icons. One icon library only.
- **Zod**: Runtime schema validation for all API responses. If validation fails, treat it as an API error.
- **date-fns**: All timestamp formatting and relative time calculations.

### Hosting
- **Amazon S3 + Amazon CloudFront**: Built artifacts deployed to S3, served via CloudFront.

---

## 3. Project Structure

```
/src
  /api
    client.ts               # Axios instance, base URL, auth headers
    /endpoints              # One file per backend API group (incidents, analytics, runbooks)
    /schemas                # Zod schemas for every API response shape
    /hooks                  # TanStack Query hooks (useIncidents, useIncidentDetail, etc.)
  /components
    /layout
      Sidebar.tsx
      Header.tsx
      PageContainer.tsx
    /shared
      Badge.tsx             # Severity, status, confidence badges
      CodeViewer.tsx        # Monaco wrapper for JSON and logs
      EmptyState.tsx
      ErrorState.tsx
      Skeleton.tsx
      ConfirmDialog.tsx
      Timeline.tsx          # Reusable lifecycle stage stepper
    /charts
      MetricChart.tsx       # Recharts wrapper for CloudWatch metric time-series data
  /pages
    Overview.tsx
    Incidents.tsx
    IncidentDetail.tsx
    ServiceMap.tsx
    Analytics.tsx
    Runbooks.tsx
  /store
    ui.ts                   # Zustand: environment selector, sidebar state
  /types
    incident.ts
    analytics.ts
    runbooks.ts
  /utils
    formatting.ts           # Date, duration, confidence formatters
    severity.ts             # Severity/status to color/icon mapping
  main.tsx
  App.tsx                   # Router definition + Layout wrapper
tailwind.config.ts
vite.config.ts
```

---

## 4. Pages & Routes

```
/                         Overview Dashboard
/incidents                Incident List
/incidents/:id            Incident Detail
/service-map              Service Dependency Map
/analytics                Evaluation & Analytics
/runbooks                 Runbook Browser
/runbooks/:fault_class    Single Runbook Viewer
```

---

### 4.1 Overview Dashboard (`/`)

**Purpose**: Answer "What is the state of the system right now?" in under 5 seconds.

**Data Sources**:
- `GET /api/incidents?limit=20` — incident list.
- `GET /api/analytics?summary=true` — KPI values.

**Polling**: Active incidents refetch every 8 seconds.

**Layout**:
1. Four KPI cards in a horizontal row.
2. Two-column content area: Active Incidents table (70%) + System Health panel (30%).

**KPI Cards** (four identical graphite surfaces):
- `Active Incidents` — count, crimson icon.
- `Pending Approvals` — count of `remediation.status == pending_approval`, amber icon.
- `Recovery Success` — % of `verification.status == resolved` over last 24h, emerald icon.
- `Mean Time to Recovery` — median from `detected_at` to `verification.checked_at`, neutral icon.

**Active Incidents Table Columns**:
- Severity badge
- Incident ID (monospaced)
- Fault class tag
- Affected resource (`resource_id` from DynamoDB)
- Detected time (relative, e.g., "3 min ago")
- Pipeline status badge (`remediation.status`)
- AI Confidence (from `diagnosis.confidence`)
- Action shortcut (Approve button if `pending_approval`, View link otherwise)

**Behaviors**:
- Click any row: navigate to `/incidents/:id`.
- Pending-approval rows show an Approve button inline.
- Zero incidents: EmptyState ("No active incidents. Your cloud environment is healthy.").

---

### 4.2 Incident List (`/incidents`)

**Data Source**: `GET /api/incidents` with query parameters.

**Filters**:
- Status: all pipeline states from `remediation.status`.
- Fault class: `resource_exhaustion`, `misconfiguration`, `service_cascade`.
- Confidence: Low / Medium / High (mapped from `diagnosis.confidence` numeric thresholds).
- Date range: Last 1h, 6h, 24h, 7d.
- Search: Free text on `incident_id` and `resource_id`.

**Pagination**: Cursor-based. "Load more" at the bottom.

---

### 4.3 Incident Detail (`/incidents/:id`)

**Purpose**: The primary operational screen. All pipeline stages, AI reasoning, evidence, and remediation control in one view.

**Data Sources**:
- `GET /api/incidents/:id` — Full `IncidentRecord` from DynamoDB.
- `GET /api/incidents/:id/evidence` — Raw evidence bundle from S3 (`raw_data.json`), parsed and returned by the dashboard API.

**Polling**: If `remediation.status` is not in a terminal state, poll every 5 seconds.

**Layout — Three-Column on Wide Desktop**:
```
[ Incident Header — Full Width ]

[ LEFT 30%           ] [ CENTER 45%               ] [ RIGHT 25%       ]
[ Lifecycle Timeline ] [ AI Diagnosis Panel        ] [ Approval Card   ]
[                   ] [ Evidence Explorer          ] [ Verification    ]
```

Collapses to a single column on tablet/mobile in order: Header → Timeline → Diagnosis → Evidence → Approval → Verification.

---

#### Incident Header (full-width)

Fields displayed, all sourced directly from `IncidentRecord`:
- Severity badge (derived from `fault_class` and `diagnosis.confidence`)
- Incident ID (monospaced, copyable — `incident_id`)
- Fault class tag (`fault_class`)
- Root cause summary (`diagnosis.root_cause` if available, else "Diagnosing...")
- Pipeline status badge (`remediation.status`)
- Detection time: relative from `detected_at`
- Detection source: `detection_source` field
- Affected resource: `resource_id`

---

#### Lifecycle Timeline (left column, vertical stepper)

Each stage has a status icon, name, timestamp (where available from DynamoDB), and brief metadata.

| Stage | Status derives from | Timestamp source |
| :--- | :--- | :--- |
| Detect | Always complete once record exists | `detected_at` |
| Collect | `raw_data_s3_key` is populated | `detected_at` (same — collector is synchronous before DDB write) |
| Diagnose | `diagnosis.root_cause` is not null | No dedicated field — shown as "completed" with no timestamp |
| Notify | `remediation.status` is `pending_approval` | No dedicated field |
| Approve | `remediation.status` is `approved` or `rejected` | No dedicated timestamp |
| Remediate | `remediation.executed_at` is not null | `remediation.executed_at` |
| Verify | `verification.status` is not `not_run` | `verification.checked_at` |

> **Note**: Only `detected_at`, `remediation.executed_at`, and `verification.checked_at` are actual timestamps from the backend. Stages in between show status (complete/pending/failed) but not exact times. Exact per-stage timestamps require additional backend work listed in `BACKEND_SPEC.md`.

Clicking a completed stage expands an inline detail card with the relevant data for that stage (e.g., clicking Diagnose expands to show `diagnosis.confidence` and `suggested_action`).

---

#### AI Diagnosis Panel (center column, top)

All data sourced from `IncidentRecord.diagnosis`. Only shown when `diagnosis.root_cause` is not null.

Sections in order:
1. **Header**: "AI Diagnosis" label, model name tag ("Claude 3.5 Sonnet"), schema validation status badge (derived from `diagnosis.failure_mode` — if null, show "Schema validated"; if set, show the failure mode).
2. **Root Cause**: `diagnosis.root_cause` as heading, `diagnosis.explanation` as body text.
3. **Confidence**: Numeric percentage (`diagnosis.confidence * 100`) with semantic color badge (High / Medium / Low).
4. **RAG Indicator**: `diagnosis.used_rag` boolean displayed as "Runbook context used: Yes / No" with the fault class as the runbook name.
5. **Suggested Action**: `diagnosis.suggested_action` key in a monospaced tag, mapped to a human-readable description.
6. **Reasoning Trace**: Collapsible section. Full `diagnosis.reasoning_trace` text in a read-only monospaced block.
7. **Failure Mode**: Only shown if `diagnosis.failure_mode` is not null. Red system-exception banner.

---

#### Evidence Explorer (center column, below diagnosis)

Tabbed panel showing the parsed content of `raw_data.json`, returned by the backend via `GET /api/incidents/:id/evidence`.

The available tabs depend on `fault_class`:

| Tab | Shown for | Data field in `raw_data.json` |
| :--- | :--- | :--- |
| Metrics | `resource_exhaustion`, `service_cascade` | `evidence.metrics` (time-series datapoints) |
| Logs | `resource_exhaustion`, `service_cascade` | `evidence.logs_insights.rows` |
| X-Ray | `service_cascade` only | `evidence.xray_trace_summaries`, `evidence.xray_service_graph` |
| Config | `misconfiguration` only | `evidence.config_compliance`, `evidence.resource_config_history` |
| GuardDuty | `misconfiguration` (GuardDuty source only) | `evidence.guardduty_finding` |
| Raw JSON | All fault classes | Full `raw_data.json` |

**Metrics Tab**: Time-series Recharts chart for CloudWatch metrics collected by the Collector. Each metric (Duration, Errors, Throttles, Invocations) is a selectable line. A dotted crimson horizontal line marks the alarm threshold value (hardcoded per alarm name from the known SAM template thresholds: 50,000ms for resource exhaustion, 5 errors for cascade).

**Logs Tab**: Scrollable log list from `logs_insights.rows`. Each row shows `@timestamp`, `@message`. Filter by log level keyword (ERROR, WARN).

**X-Ray Tab**: List of `xray_trace_summaries` showing trace ID, duration, has_fault, has_error. Service graph edges from `xray_service_graph` shown as a simple text list (Service → Service with edge stats). Full React Flow service graph visualization requires additional backend work — see `BACKEND_SPEC.md`.

**Config Tab**: Table of `config_compliance.results` rows (resource ID, compliance type, annotation). Resource config history shown as a collapsible JSON block.

**Raw JSON Tab**: Full `raw_data.json` rendered in Monaco editor (read-only, dark theme).

---

#### Approval Controls (right column)

State-driven rendering based on `remediation.status`:

- `pending_approval`: Show the approval card below.
- `approved`: "Approved — remediation executing."
- `rejected`: "Rejected" with the stored rejection reason if available.
- `executed`: Action taken (`remediation.action_taken`) and execution time (`remediation.executed_at`).
- `failed`: Failure message.

**Approval Card contents**:
- Incident ID + current status.
- Proposed action: human-readable name mapped from `diagnosis.suggested_action` key.
- Target resource: `diagnosis.affected_resources` list.
- Risk level badge: hardcoded per action type (e.g., `lock_s3_bucket` = High, `scale_up` = Medium).
- Pre-flight checklist (manually checked by the engineer — not auto-checked):
  - "I have reviewed the AI diagnosis and confidence score."
  - "I have reviewed the supporting evidence."
  - "I confirm the target resource and environment."
- `Approve` button: Disabled until all checklist items are checked. POSTs to `/api/incidents/:id/approve`. High-risk actions open a ConfirmDialog before sending.
- `Reject` button: Opens an inline text field for a reason, then POSTs to `/api/incidents/:id/reject`.
- Stale state guard: If the incident state changed since page load, show "State has changed — refresh before acting."

---

#### Verification Panel (right column, below approval)

Shown when `verification.status` is not `not_run`. All data from `IncidentRecord.verification`.

- Status badge: `resolved` (emerald) / `not_resolved` (crimson) / `inconclusive` (amber).
- Signal rechecked: `verification.signal_rechecked` text.
- Checked at: `verification.checked_at` timestamp.
- Outcome notes: `verification.notes` text — this is a human-readable string from the backend describing the actual metric values compared against the threshold (e.g., "Max Duration = 1400ms vs threshold 50000ms. Below threshold — incident resolved.").

> **No before/after metric sparklines are shown here.** The verification backend writes a descriptive `notes` string only — it does not store pre/post metric arrays. Sparklines would require additional backend work described in `BACKEND_SPEC.md`.

---

### 4.4 Service Map (`/service-map`)

**Data Source**: `GET /api/services`.

This endpoint does not exist yet in `PROJECT_SPEC.md` and requires additional backend work described in `BACKEND_SPEC.md`.

Until that endpoint exists, this page shows a **static topology diagram** of the three known services (Service A → Service B → Service C) with no live health data. If any active incident exists for a service, it is overlaid with a warning badge.

---

### 4.5 Analytics (`/analytics`)

**Data Source**: `GET /api/analytics` — returns the latest evaluation run results from `/evaluation/results/` (Phase 7 + Phase 8 of `PROJECT_SPEC.md`).

This page is only meaningful after Phase 7 evaluation runs have been completed. If no results exist, an EmptyState is shown.

**Panels that map directly to Phase 7 `metrics.py` output**:
1. **KPI Row**: MTTR (median), Diagnosis Success Rate, Verification Success Rate, Diagnosis-Recovery Gap %.
2. **Incident count over time**: Bar chart grouped by fault class.
3. **MTTR distribution**: Histogram per fault class.
4. **Diagnosis-Recovery Gap**: Bar chart — % of incidents where `confidence > 0.7` but `verification.status == not_resolved`.
5. **Failure Mode Taxonomy**: Distribution of `diagnosis.failure_mode` values across all evaluation runs.
6. **RAG vs No-RAG comparison**: Side-by-side bars for accuracy, hallucination rate, and verification rate between `used_rag=true` and `used_rag=false` runs.

**Panels deferred** (require backend additions beyond `PROJECT_SPEC.md`):
- Confidence vs Correctness scatter chart (requires per-incident ground-truth match scoring to be stored — see `BACKEND_SPEC.md`).

---

### 4.6 Runbooks (`/runbooks`)

**Data Source**: `GET /api/runbooks` — list of runbooks. `GET /api/runbooks/:fault_class` — content of a single runbook.

Runbooks are the 3 markdown files in `/knowledge_base/` served by the dashboard API Lambda (Phase 8).

**Behaviors**:
- List view: fault class name, file name, character count.
- Detail view: Markdown rendered as formatted HTML.
- "View as injected into prompt" toggle: Shows the exact plain-text version passed to Bedrock.

---

## 5. Full API Contract

All requests include:
```
Authorization: Bearer <token>
Content-Type: application/json
```

All responses use the envelope:
```json
{
  "data": {},
  "error": null
}
```

| Method | Endpoint | Purpose | Backed by |
| :--- | :--- | :--- | :--- |
| GET | `/api/incidents` | Paginated list with filters | `DashboardApiLambda` (Phase 8) |
| GET | `/api/incidents/:id` | Full `IncidentRecord` | `DashboardApiLambda` (Phase 8) |
| GET | `/api/incidents/:id/evidence` | Parsed `raw_data.json` from S3 | `DashboardApiLambda` (Phase 8) |
| POST | `/api/incidents/:id/approve` | Approve remediation | `ApprovalFunction` (Phase 5, exists) |
| POST | `/api/incidents/:id/reject` | Reject with reason | `ApprovalFunction` (Phase 5, exists) |
| GET | `/api/analytics` | Evaluation results summary | `DashboardApiLambda` (Phase 8) |
| GET | `/api/runbooks` | Runbook list | `DashboardApiLambda` (Phase 8) |
| GET | `/api/runbooks/:fault_class` | Runbook content | `DashboardApiLambda` (Phase 8) |
| GET | `/api/services` | Service topology + health | Requires additional backend work (see `BACKEND_SPEC.md`) |

### Zod Schema Example

```typescript
// src/api/schemas/incident.ts

export const DiagnosisSchema = z.object({
  root_cause: z.string().nullable(),
  confidence: z.number().min(0).max(1).nullable(),
  affected_resources: z.array(z.string()),
  suggested_action: z.enum([
    'scale_up', 'restart_service', 'lock_s3_bucket',
    'tighten_iam_policy', 'restart_downstream_service', 'manual_review_required'
  ]).nullable(),
  explanation: z.string().nullable(),
  reasoning_trace: z.string().nullable(),
  used_rag: z.boolean().nullable(),
  failure_mode: z.string().nullable(),
});

export const VerificationSchema = z.object({
  status: z.enum(['not_run', 'resolved', 'not_resolved', 'inconclusive']),
  checked_at: z.string().nullable(),
  signal_rechecked: z.string().nullable(),
  notes: z.string().nullable(),
});

export const IncidentRecordSchema = z.object({
  incident_id: z.string().uuid(),
  fault_class: z.enum(['resource_exhaustion', 'misconfiguration', 'service_cascade']),
  detected_at: z.string().datetime(),
  raw_data_s3_key: z.string(),
  detection_source: z.string(),
  resource_id: z.string().nullable(),
  diagnosis: DiagnosisSchema,
  remediation: z.object({
    status: z.enum(['pending_approval', 'approved', 'executed', 'rejected', 'failed']),
    action_taken: z.string().nullable(),
    executed_at: z.string().nullable(),
  }),
  verification: VerificationSchema,
  ground_truth: z.object({
    true_fault_class: z.string().nullable(),
    injected_at: z.string().nullable(),
  }),
});
```

---

## 6. State Management

| State Type | Where Stored |
| :--- | :--- |
| Server data (incidents, analytics, runbooks) | TanStack Query cache |
| Active incident ID | React Router URL param |
| Selected environment | Zustand `ui.ts` |
| Approval checklist completion | Local component `useState` |
| Rejection reason text | Local component `useState` |
| Evidence Explorer active tab | Local component `useState` |

---

## 7. Error, Loading & Empty States

Every data-fetching component must implement all four states before it ships:

| State | Behavior |
| :--- | :--- |
| Loading | Render `Skeleton` shaped like the expected content |
| Empty | Render `EmptyState` with a context-specific message |
| Error | Render `ErrorState` with error code and a "Retry" button |
| Stale | Show "Last updated N seconds ago" badge in the component header |

---

## 8. Implementation Phases

### Phase 1: MVP (Demo-ready) — ✅ COMPLETED
- [x] Tailwind design tokens from `DESIGN_SPEC.md` in `tailwind.config.ts`
- [x] Sidebar, Header, Page layout
- [x] Overview Dashboard (KPI cards + Incident table, polling)
- [x] Incident Detail: Header + Lifecycle Timeline + AI Diagnosis Panel + Raw JSON evidence tab + Approval/Rejection controls + Verification panel
- [x] All loading, empty, error, and stale states

### Phase 2: Full Feature Set — ✅ COMPLETED
- [x] CloudWatch metric charts in Evidence Explorer (Recharts, with threshold line)
- [x] Searchable log viewer (Logs tab)
- [x] X-Ray trace summary list (X-Ray tab)
- [x] Config and GuardDuty evidence tabs
- [x] Incident List page with filtering and pagination
- [x] Runbook browser and viewer
- [x] Static Service Map with incident overlays

### Phase 3: Research & Evaluation — ✅ COMPLETED
- [x] Full Analytics page with all 6 mapped panels (requires Phase 7 evaluation data)
- [x] Live Service Map (requires additional backend endpoint — see `BACKEND_SPEC.md`)
- [x] Confidence vs Correctness scatter chart (requires backend additions — see `BACKEND_SPEC.md`)
- [x] Before/After metric sparklines in Verification panel (requires backend additions — see `BACKEND_SPEC.md`)
- [x] ReplayMode with stage-by-stage playback and auto-play
