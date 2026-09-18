# Prompt: Rebuild the Phase 8 Dashboard Frontend — Complete Functional Flow

## What You Are Working On

This is an LLM-Assisted Cloud Incident Response system on AWS. The backend (Phases 0–7) is **fully deployed and working**. The frontend exists in `dashboard/web/` but currently shows no data and has no way to trigger the incident pipeline from the UI. Your job is to fix and redesign it so a user can run the complete flow end to end from the browser with minimal button clicks.

---

## Step 0 — Do This First (Setup)

### 0a. Create the env file

Create `dashboard/web/.env`:
```
VITE_API_BASE_URL=https://0jqdaxn8k1.execute-api.ap-south-1.amazonaws.com/Prod
```

### 0b. Verify the API is live

These endpoints are deployed and returning real data right now:

```bash
# Returns 10 real incidents from DynamoDB
curl https://0jqdaxn8k1.execute-api.ap-south-1.amazonaws.com/Prod/incidents

# Returns full incident detail + raw S3 data
curl https://0jqdaxn8k1.execute-api.ap-south-1.amazonaws.com/Prod/incidents/472e4043-e7af-4782-9c33-ea53520eaa3a

# Returns evaluation metrics
curl https://0jqdaxn8k1.execute-api.ap-south-1.amazonaws.com/Prod/results
```

### 0c. Install dependencies and start dev server

```bash
cd dashboard/web
npm install
npm run dev
```

The dev server runs on `http://localhost:3000`.

---

## The Core Problem to Fix

The current frontend has four issues:

1. **No `.env` file** — `VITE_API_BASE_URL` is undefined so every API call silently fails
2. **No fault injection trigger** — there is no button to kick off an incident; users cannot start the pipeline from the UI
3. **Data renders as "—" or empty** — the incident records in DynamoDB have `diagnosis.root_cause: null` for most records because the diagnosis Lambda did not run to completion; the UI must handle null fields gracefully and still show what data exists
4. **No manual diagnosis trigger** — when diagnosis is null, there must be a way to re-trigger it

---

## Live Data State Right Now

The API returns 10 real incidents. Here is what they look like:

| Incident (first 8 chars) | Fault Class | Remediation Status | Diagnosis |
|---|---|---|---|
| `472e4043` | resource_exhaustion | pending_approval | null |
| `2d68a242` | resource_exhaustion | failed | ✅ Has root cause |
| `4b865b20` | resource_exhaustion | failed | ✅ Has root cause |
| `4daafee3` | service_cascade | pending_approval | null |
| `6271a288` | misconfiguration | pending_approval | null |
| 5 others | resource_exhaustion | pending_approval | null |

The UI must display all of these correctly, including the ones with null diagnosis.

---

## What to Build: The Complete User Flow

A user visiting the dashboard must be able to complete this entire flow with the minimum number of clicks:

```
[Trigger Fault] → [Watch Detection] → [See Diagnosis] → [Approve Remediation] → [See Verification]
```

Every step must be visible in the UI. Design it as a **single-page control panel** — the user should not need to navigate away from the main view to complete the flow.

---

## Page-by-Page Specification

### Page 1 — Overview (`/`)

This is the main page. It must contain everything needed to run the complete flow.

**Section A — Fault Injection Panel (NEW — this is the most important missing piece)**

A card at the top of the page with the heading "Trigger Fault Injection". Contains three buttons, one per fault class:

```
[ Trigger Resource Exhaustion ]  [ Trigger Misconfiguration ]  [ Trigger Service Cascade ]
```

When a button is clicked:
- Show a loading spinner on that button
- Call `POST /inject` on the backend (see "New Backend Endpoint" section below)
- On success: show a green toast/banner — "Fault injected. Watch the incident feed for detection." and auto-scroll to the incident feed
- On error: show a red toast/banner with the error message
- Disable all three buttons for 10 seconds after any injection to prevent double-triggering

**Section B — KPI Row**

Four stat cards in a row. Pull data from `GET /incidents`. All must handle zero/null gracefully:

- **Active Incidents** — count of incidents where `remediation.status` is not `executed` and `verification.status` is not `resolved`
- **Pending Approvals** — count where `remediation.status === 'pending_approval'`
- **Recovery Rate** — `(resolved / total) * 100`%
- **Avg MTTR** — average minutes between `detected_at` and `verification.checked_at` for resolved incidents; show "—" if no resolved incidents yet

**Section C — Incident Feed Table**

A live-polling table (refresh every 5 seconds). Columns:

| Column | Content |
|--------|---------|
| Severity | `Critical` (red badge) or `Warning` (amber badge) based on fault class |
| Incident ID | First 8 chars of UUID in monospace |
| Fault Class | Human-readable: "Resource Exhaustion", "Misconfiguration", "Service Cascade" |
| Status | Pipeline stage badge (see status badge colours below) |
| Detected | Relative time ("3 min ago") with full timestamp on hover |
| Diagnosis | Root cause text truncated to 60 chars, or "Diagnosing..." with a pulsing dot if null |
| Actions | One icon button: "View Details" arrow → navigates to `/incidents/:id` |

Clicking any row also navigates to the detail page.

**Status badge colours (strictly these — no other colours):**
- `detected` → gray background, gray text
- `diagnosing` → dark background, purple-ish text (`#7C7CFF`)
- `pending_approval` → amber surface background, amber text
- `approved` → emerald surface, emerald text
- `executed` → emerald surface, emerald text
- `resolved` → emerald surface, emerald text
- `not_resolved` → crimson surface, crimson text
- `failed` → crimson surface, crimson text

**Empty state:** "No active incidents. Your cloud environment is healthy." with a green checkmark icon.

---

### Page 2 — Incident Detail (`/incidents/:incidentId`)

Three-column layout. This page must show all available data and handle null fields gracefully.

**Header (full width)**
- Severity badge + fault class
- First 8 chars of incident ID in monospace
- Pipeline status badge
- Detected timestamp
- "← Back" button

**Left column (25%) — Lifecycle Timeline**

Vertical stepper with 6 stages. Each stage node:
- ✅ Green filled circle + checkmark = complete
- 🟡 Amber pulsing circle = in progress  
- ⭕ Hollow circle = not started yet
- ❌ Red circle = failed

Stages and when they are "complete":
1. **Detect** — always complete once incident exists (`detected_at` is set)
2. **Collect** — complete when `raw_data_s3_key` is set
3. **Diagnose** — complete when `diagnosis.root_cause` is not null
4. **Approve** — complete when `remediation.status` is `approved` or `executed`; "in progress" when `pending_approval`; "failed" when `rejected`
5. **Remediate** — complete when `remediation.status` is `executed`; "failed" when `failed`
6. **Verify** — complete when `verification.status` is `resolved`; "failed" when `not_resolved`

**Center column (50%) — Data panels**

Panel 1 — **AI Diagnosis**
- If `diagnosis.root_cause` is null: show "Diagnosis pending..." with a pulsing amber indicator and a "Re-trigger Diagnosis" button (calls `POST /diagnose` — see backend section)
- If populated: show root cause, confidence badge (High ≥90% green / Medium ≥70% amber / Low <70% red), suggested action in monospace, reasoning trace in a scrollable code block with monospace font, used-RAG indicator

Panel 2 — **Evidence Explorer** (tabbed)
- **Metrics tab** — show CloudWatch metrics data from `raw_data.cloudwatch_metrics` if present, otherwise "No metrics data"
- **Logs tab** — show log lines from `raw_data.log_data` if present
- **X-Ray tab** — show trace data from `raw_data.xray_traces` if present
- **Raw JSON tab** — pretty-print the entire `raw_data` object

All tabs: if data is null/empty show "No data collected" with the eye-off icon, not a blank screen.

**Right column (25%) — Action panels**

Panel 1 — **Approval**
- If `remediation.status === 'pending_approval'`: show amber warning banner "Awaiting approval", "Approve" button (danger red), "Reject" button (ghost)
  - Approve: opens `https://0jqdaxn8k1.execute-api.ap-south-1.amazonaws.com/Prod/approval?incident_id=<id>&action=approve` in a new tab
  - Reject: opens the same URL with `action=reject` in a new tab
  - Note below buttons: "Approval processed via Phase 5 endpoint. This dashboard is read-only."
- If already approved/executed: green checkmark + "Approved"
- If rejected: gray "Rejected"
- If no diagnosis yet: gray "Waiting for diagnosis"

Panel 2 — **Verification**
- If `verification.status === 'not_run'` and remediation has not executed yet: "Verification will run automatically after remediation"
- If `verification.status === 'resolved'`: green banner "Signal resolved — incident closed"
- If `verification.status === 'not_resolved'`: red banner "Signal still firing — remediation did not resolve the incident"
- If `verification.status === 'inconclusive'`: amber banner "Inconclusive — check manually"
- Always show `verification.signal_rechecked` and `verification.notes` if present

---

### Page 3 — Analytics (`/analytics`)

Already mostly implemented. Fix two things:

1. All chart empty states must show a clear message and icon, not a blank white box
2. KPI cards must not show `NaN%` or `undefined` — show `—` for any missing/zero data

---

### Page 4 — Replay (`/replay`)

A demo mode for presentations. Simple implementation:

1. A dropdown listing all incident IDs from `GET /incidents` — label each as `<fault_class> — <first 8 chars of id> — <detected_at date>`
2. After selecting an incident, a "Load Incident" button fetches the full detail
3. A stepper: **← Prev Stage** | **Stage 2 of 6: Collect** | **Next Stage →**
4. Below the stepper: render the same 3-column Incident Detail view but freeze it at the current stage — hide all data that belongs to later stages
5. An **Auto-Play** button that advances one stage every 3 seconds automatically. Auto-play stops when it reaches stage 6.

Stage reveal rules (what to show at each step):
- Stage 1 (Detect): header + timeline only, everything else blank/hidden
- Stage 2 (Collect): reveal Evidence Explorer tabs
- Stage 3 (Diagnose): reveal Diagnosis panel
- Stage 4 (Approve): reveal Approval card
- Stage 5 (Remediate): show remediation executed state
- Stage 6 (Verify): reveal Verification card with final result

---

## New Backend Endpoints to Add

Add two new endpoints to `src/dashboard/app.py`. These allow the UI to trigger pipeline actions that don't require IAM write access on the dashboard's own role — they invoke the existing Lambdas.

### `POST /inject`

Accepts JSON body: `{ "fault_class": "resource_exhaustion" | "misconfiguration" | "service_cascade" }`

Implementation:
- Invokes the **Collector Lambda** (`llm-incident-response-CollectorFunction-vsUPnwh07wOT`) with a synthetic EventBridge-style payload
- The payload to send to the Collector:

```json
{
  "source": "dashboard_injection",
  "fault_class": "<fault_class from request body>",
  "alarm_name": "manual-dashboard-trigger",
  "state": "ALARM",
  "reason": "Manual fault injection triggered from dashboard"
}
```

- Returns `{ "incident_id": "<uuid>", "message": "Fault injection triggered" }` on success
- The `DashboardRole` in `template.yaml` needs one additional permission added:
  ```yaml
  - Effect: Allow
    Action:
      - lambda:InvokeFunction
    Resource:
      - arn:aws:lambda:ap-south-1:889081505756:function:llm-incident-response-CollectorFunction-vsUPnwh07wOT
  ```

### `POST /diagnose`

Accepts JSON body: `{ "incident_id": "<uuid>" }`

Implementation:
- Invokes the **Diagnosis Lambda** (`llm-incident-response-DiagnosisFunction-zuevkfvASCie`) with: `{ "incident_id": "<id>" }`
- Returns `{ "message": "Diagnosis triggered" }` on success
- Add permission to `DashboardRole`:
  ```yaml
  - Effect: Allow
    Action:
      - lambda:InvokeFunction
    Resource:
      - arn:aws:lambda:ap-south-1:889081505756:function:llm-incident-response-DiagnosisFunction-zuevkfvASCie
  ```

Both are fire-and-forget (`InvocationType='Event'`) — they return immediately, the actual work happens async and the incident feed polls for the result.

Add both routes to the API Gateway in `infra/template.yaml` under `DashboardFunction.Events`.

---

## Design Rules — Obsidian Command

Read `DESIGN_SPEC.md` for the full spec. The non-negotiables:

**Colours — only these:**
| Role | Value |
|---|---|
| Page background | `#050505` |
| Cards / panels | `#111113` |
| Hover / elevated | `#1B1B1F` |
| Primary text | `#F2F2F2` |
| Secondary text | `#85858C` |
| Muted text | `#55555D` |
| Critical / danger | `#D63C4B` (crimson) |
| Warning / pending | `#F0A23A` (amber) |
| Success / healthy | `#46B887` (emerald) |
| Card borders | `#2A2A2D` |

**Never use:** bright blue, purple, cyan, gradients, neon, white backgrounds, colored card backgrounds.

**Typography:** Inter for all text. JetBrains Mono for incident IDs, timestamps, JSON, metric names.

**Cards:** `background: #111113`, `border: 1px solid #2A2A2D`, `border-radius: 6px`. No box shadows.

**Buttons:**
- Danger (approve): `background: #321419`, `border: 1px solid #7A1E27`, `color: #D63C4B`
- Ghost (reject/cancel): no background, `border: 1px solid #2A2A2D`, `color: #85858C`
- Primary (default): `background: #1B1B1F`, `border: 1px solid #3A3A3E`, `color: #F2F2F2`

---

## Deploy After Changes

Any change to `src/dashboard/app.py` or `infra/template.yaml` requires a redeploy:

```bash
cd infra
sam build
sam deploy
```

Any change to frontend files only requires saving — Vite hot-reloads automatically.

---

## File Map

```
infra/template.yaml                    ← Add POST /inject and POST /diagnose routes + Lambda invoke permissions to DashboardRole

src/dashboard/app.py                   ← Add handle_inject() and handle_diagnose() handlers

dashboard/web/.env                     ← CREATE THIS (see Step 0)

dashboard/web/src/
  config/api.js                        ← Add injectFault(faultClass) and triggerDiagnosis(incidentId) methods
  pages/Overview.jsx                   ← Add FaultInjectionPanel section; fix KPI null handling
  components/IncidentFeed.jsx          ← Fix null diagnosis display; handle all null fields gracefully
  pages/IncidentDetail.jsx             ← Fix null diagnosis panel; wire approve/reject buttons; fix all null states
  pages/Analytics.jsx                  ← Fix NaN/undefined in KPI cards; fix empty chart states
  pages/ReplayMode.jsx                 ← Implement stage-by-stage replay with auto-play
```

---

## Definition of Done

The task is complete when a user can open the browser and:

1. Click "Trigger Resource Exhaustion" → see a new incident appear in the feed within 30 seconds
2. Click that incident → see the 3-column detail view with whatever data has been collected
3. See the lifecycle timeline update as diagnosis runs
4. Click "Approve" → be taken to the approval URL, approve it, come back, see status update to `approved` then `executed` on next poll
5. See the verification result appear automatically
6. No blank screens, no `undefined`, no `NaN`, no empty white boxes anywhere in the app
