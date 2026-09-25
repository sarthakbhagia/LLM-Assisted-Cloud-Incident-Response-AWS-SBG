# Phase 8 — Presentation Dashboard: Handoff Document

## Context

This project is an LLM-Assisted Cloud Incident Response system running on AWS.
Phases 0–7 are fully deployed and working in `ap-south-1` (account `889081505756`).
Phase 8 adds a read-only presentation dashboard. Implementation is **partially complete**.

Refer to `PROJECT_SPEC.md` (step 28–31) for functional requirements and `DESIGN_SPEC.md` for the complete visual/component specification (Obsidian Command design system).

---

## What Has Been Implemented

### Backend — `src/dashboard/app.py`

Read-only Lambda API with four endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/incidents` | Paginated list. Query params: `limit`, `lastKey`, `status`, `faultClass` |
| GET | `/incidents/{incident_id}` | Full incident record + raw S3 evidence bundle |
| GET | `/results` | Evaluation results from S3; falls back to live-computed metrics |
| GET | `/health` | Health check |

All responses include CORS headers. No write operations anywhere.

### Infrastructure — `infra/template.yaml`

Added at the bottom of the Resources section (before Outputs):

- **`DashboardFunction`** — Lambda pointing at `../src/dashboard/`, handler `app.lambda_handler`
- **`DashboardRole`** — Strictly read-only IAM role:
  - DynamoDB: `GetItem`, `Query`, `Scan` on `incidents-dev` table only
  - S3: `GetObject` on `incidents/*` and `evaluation/*` prefixes only
  - No approval, remediation, or write permissions — hard guardrail per spec
- **API Gateway routes** — GET + OPTIONS for all four endpoints wired to `DashboardFunction`
- **Outputs added**: `DashboardFunctionArn`, `DashboardApiUrl`

### Frontend — `dashboard/web/`

#### Project scaffold
| File | Purpose |
|------|---------|
| `package.json` | React 18, React Router 6, Recharts, Lucide React, date-fns, Tailwind CSS 3, Vite 4 |
| `vite.config.js` | Dev server on port 3000 |
| `index.html` | Inter + JetBrains Mono fonts from Google Fonts |
| `tailwind.config.js` | Full Obsidian Command token system mapped to Tailwind (`bg-bg-base`, `text-crimson`, `bg-amber-surface`, etc.) |
| `postcss.config.js` | Tailwind + Autoprefixer |
| `src/main.jsx` | React root with `BrowserRouter` |
| `src/index.css` | Global styles: `.card`, `.btn-primary`, `.btn-danger`, `.btn-ghost`, `.badge`, `.badge-critical`, `.badge-warning`, `.badge-success`, `.table`, `.table-row`, `.mono`, `.pulse-loading` |
| `src/App.jsx` | Routes: `/`, `/incidents/:incidentId`, `/analytics`, `/replay`, `/replay/:incidentId` |

#### Utilities
| File | Contents |
|------|---------|
| `src/config/api.js` | `ApiClient` class, `VITE_API_BASE_URL` env var, named methods `getIncidents()`, `getIncidentDetail()`, `getResults()` |
| `src/utils/constants.js` | `FAULT_CLASSES`, `REMEDIATION_STATUSES`, `VERIFICATION_STATUSES`, `PIPELINE_STAGES`, `CONFIDENCE_LEVELS`, `POLLING_INTERVALS` |
| `src/utils/helpers.js` | `getIncidentStatus()`, `getPipelineStageStatus()`, `getConfidenceLevel()`, `formatDate()`, `formatMTTR()`, `calculateMTTR()`, `getSeverityFromFaultClass()` |

#### Components & Pages
| File | Status | Description |
|------|--------|-------------|
| `src/components/Layout.jsx` | ✅ Done | Sidebar (collapsible, crimson active-border), 48px header, nav links to all pages |
| `src/components/IncidentFeed.jsx` | ✅ Done | Live-polling table (5s interval), `status` + `faultClass` filters, severity/confidence badges, skeleton loader, empty state |
| `src/pages/Overview.jsx` | ✅ Done | 4 KPI cards (Active Incidents, Pending Approvals, Recovery Success, Avg MTTR), `IncidentFeed`, System Health panel, Recent Remediations panel |
| `src/pages/IncidentDetail.jsx` | ✅ Done | 3-column layout per design spec — see detail below |
| `src/pages/Analytics.jsx` | ✅ Done | 4 KPI cards + 6 Recharts charts — see detail below |
| `src/pages/ReplayMode.jsx` | ❌ **MISSING** | Entire file not created — see spec below |

#### IncidentDetail layout (3-column per `DESIGN_SPEC.md` §7.2)
- **Left (30%)** — `LifecycleTimeline`: 6 pipeline stages (Detect → Collect → Diagnose → Approve → Remediate → Verify), expandable inline sub-cards, pulsing amber for in-progress, crimson for failed, emerald for complete
- **Center (45%)** — `DiagnosisPanel`: root cause, confidence badge (High/Medium/Low with colour), used-RAG flag, suggested action, reasoning trace in monospaced code block. Below it: `EvidenceExplorer` with 4 tabs (Metrics / Logs / X-Ray / JSON)
- **Right (25%)** — `ApprovalCard`: approve/reject buttons rendered but **not wired to any API** (see TODO below). `VerificationCard`: resolved/not_resolved/inconclusive with colour-coded banner

#### Analytics charts (6 total, all using Obsidian palette)
1. **Incident Timeline** — stacked bar by fault class, last 14 days
2. **MTTR Distribution** — histogram with minute buckets
3. **Confidence vs Correctness** — scatter plot with 70% reference line
4. **Diagnosis-Recovery Gap** — horizontal stacked bar (resolved vs not_resolved for high-confidence diagnoses), crimson border highlight
5. **Failure Mode Taxonomy** — horizontal bar of `diagnosis.failure_mode` values
6. **RAG vs No-RAG** — grouped bar comparing accuracy with/without runbook context injection

All chart data is derived live from the incidents list when evaluation result files aren't in S3 yet.

---

## What Is Left To Do

### 1. `ReplayMode` page — `src/pages/ReplayMode.jsx` ❌ ENTIRE FILE MISSING

This is the demo presentation tool. Per `PROJECT_SPEC.md` step 31:

> "lets you pick a past incident_id from an evaluation run and step through its state transitions at a controlled pace (e.g., 1 stage every 3 seconds), so the demo doesn't depend on a live fault injection completing cleanly in front of an audience"

**Required behaviour:**
- Dropdown/search to select any `incident_id` from the incidents list (fetched from `GET /incidents`)
- Speed control: 1s / 3s / 5s per stage (3s default)
- **Play / Pause / Reset** controls
- Progress bar showing current stage out of 6
- At each step render the same 3-column layout from `IncidentDetail.jsx` but with state **frozen to that step** — mask all later pipeline stages as "Not Started", hide diagnosis/verification data until the step that reveals them
- Stage sequence to replay:
  1. `detected` — show incident header only
  2. `evidence_collected` — show evidence explorer populated
  3. `diagnosed` — reveal DiagnosisPanel
  4. `pending_approval` — reveal ApprovalCard in pending state
  5. `executed` — show remediation executed
  6. `verified` — reveal VerificationCard with final outcome
- Route: `/replay` (pick incident) and `/replay/:incidentId` (jump straight to replay for a specific incident)
- No new API calls needed — reuse `apiClient.getIncidents()` and `apiClient.getIncidentDetail()`

**Suggested component structure:**
```
ReplayMode
├── IncidentPicker      (dropdown, loads from GET /incidents)
├── ReplayControls      (Play/Pause/Reset, speed selector, stage progress bar)
└── ReplayStageView     (renders frozen IncidentDetail view for currentStage)
    ├── LifecycleTimeline   (reuse from IncidentDetail, pass frozen stage index)
    ├── DiagnosisPanel      (hidden until stage >= 3)
    ├── EvidenceExplorer    (hidden until stage >= 2)
    ├── ApprovalCard        (hidden until stage >= 4)
    └── VerificationCard    (hidden until stage >= 6)
```

---

### 2. Wire Approve/Reject buttons in `ApprovalCard`

Currently the buttons render but do nothing. Two options — pick one:

**Option A (recommended for read-only dashboard):** Make the Approve button open the existing Phase 5 approval URL in a new tab:
```
https://o212lf1md4.execute-api.ap-south-1.amazonaws.com/Prod/approval?incident_id=<id>&action=approve
```
Add a tooltip: "Opens Phase 5 approval endpoint". The dashboard stays purely read-only.

**Option B:** Disable both buttons with `opacity-40 cursor-not-allowed` and add a tooltip: "Use the Slack link to approve. Dashboard is read-only."

---

### 3. Create `.env` files

`frontend/.env` does not exist. Create it:
```
VITE_API_BASE_URL=https://o212lf1md4.execute-api.ap-south-1.amazonaws.com/Prod
```

Also create `dashboard/web/.env.example`:
```
VITE_API_BASE_URL=https://<api-id>.execute-api.<region>.amazonaws.com/Prod
```

Add `.env` to `dashboard/web/.gitignore` (or the root `.gitignore`).

---

### 4. Run `npm install`

Dependencies have never been installed. Run inside `dashboard/web/`:
```bash
npm install
```
Then verify dev server starts:
```bash
npm run dev
```

---

### 5. Deploy the dashboard Lambda to AWS

The `DashboardFunction` is defined in `template.yaml` but not yet deployed. From the `infra/` directory:
```bash
sam build
sam deploy
```

After deploy, check the new output `DashboardApiUrl` in the CloudFormation stack outputs and confirm it matches the URL in `.env`.

---

### 6. End-to-end smoke test

After steps 4 and 5:

1. Hit `GET /incidents` directly and confirm real records return from DynamoDB
2. Hit `GET /incidents/<id>` and confirm `raw_data` from S3 is included
3. Open `npm run dev` and confirm the Overview feed loads real incidents
4. Trigger a fault injection (`python fault_injection/inject_resource_exhaustion.py`) and watch the incident card progress through stages on the Overview page live
5. Click into the incident and confirm all three columns render correctly
6. Open Analytics and confirm charts render (may show empty states until evaluation harness has been run)
7. Test ReplayMode once it is implemented

---

## Key Files At A Glance

```
src/dashboard/app.py                  ← Lambda API (read-only backend)
infra/template.yaml                   ← DashboardFunction + DashboardRole added before Outputs

dashboard/web/
├── package.json
├── vite.config.js
├── index.html
├── tailwind.config.js
├── postcss.config.js
└── src/
    ├── main.jsx
    ├── index.css                     ← Obsidian Command global styles
    ├── App.jsx                       ← router
    ├── config/
    │   └── api.js                    ← API client + base URL
    ├── utils/
    │   ├── constants.js              ← status enums, polling intervals
    │   └── helpers.js                ← status/date/MTTR helpers
    ├── components/
    │   ├── Layout.jsx                ← sidebar + header
    │   └── IncidentFeed.jsx          ← live-polling table
    └── pages/
        ├── Overview.jsx              ← / route  ✅
        ├── IncidentDetail.jsx        ← /incidents/:id route  ✅
        ├── Analytics.jsx             ← /analytics route  ✅
        └── ReplayMode.jsx            ← /replay route  ❌ MISSING
```

---

## Design System Reference

All colours, typography, spacing, and component styles are defined in `DESIGN_SPEC.md`.
The Tailwind token names in `tailwind.config.js` map directly to the design spec tokens:

| Design token | Tailwind class |
|---|---|
| `--bg-base` `#050505` | `bg-bg-base` |
| `--bg-surface` `#111113` | `bg-bg-surface` |
| `--bg-elevated` `#1B1B1F` | `bg-bg-elevated` |
| `--crimson` `#D63C4B` | `text-crimson`, `border-crimson` |
| `--crimson-surface` `#321419` | `bg-crimson-surface` |
| `--amber` `#F0A23A` | `text-amber` |
| `--amber-surface` `#2B2010` | `bg-amber-surface` |
| `--emerald` `#46B887` | `text-emerald` |
| `--emerald-surface` `#0E2420` | `bg-emerald-surface` |
| `--text-primary` `#F2F2F2` | `text-text-primary` |
| `--text-secondary` `#85858C` | `text-text-secondary` |
| `--text-muted` `#55555D` | `text-text-muted` |
| `--border-subtle` `#1E1E22` | `border-border-subtle` |
| `--border-default` `#2A2A2D` | `border-border-default` |

Monospaced font (`JetBrains Mono`) is applied via the `.mono` utility class or `font-mono`.
No drop shadows on cards — elevation comes from border contrast only.
No bright blue, purple, cyan, or neon anywhere.
