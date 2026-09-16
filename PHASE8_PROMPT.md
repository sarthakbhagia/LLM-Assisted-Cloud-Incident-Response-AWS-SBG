# Prompt: Complete Phase 8 — Presentation Dashboard

## Project Overview

This is an LLM-Assisted Cloud Incident Response system on AWS. Phases 0–7 are fully deployed and working in `ap-south-1` (account `889081505756`). Phase 8 adds a read-only presentation dashboard. **Most of Phase 8 is already implemented — you are picking up a partially complete task.**

**Read `PHASE8_HANDOFF.md` first.** It has a full inventory of every file already created, what each one does, and exactly what is left. Do not re-implement anything already done.

---

## Your Task: Complete the Remaining Phase 8 Work

There are 4 things left. Do them in this order.

---

### Task 1 — Create `dashboard/web/src/pages/ReplayMode.jsx`

This is the only missing React page. It is a demo presentation tool that steps through a saved incident's pipeline stages at a controlled pace so the demo does not depend on a live fault injection completing during the presentation.

**Functional requirements (from `PROJECT_SPEC.md` step 31):**
- A dropdown/search to pick any `incident_id` from the incidents list
- Play / Pause / Reset controls
- Speed selector: 1s / 3s / 5s per stage (default 3s)
- A progress indicator showing current stage out of 6
- At each step, render the 3-column incident detail layout but with state **frozen to that step** — mask all stages after the current one as "Not Started", hide data blocks until the step that reveals them
- Routes: `/replay` (picker) and `/replay/:incidentId` (jump directly to a specific incident)

**Stage reveal sequence:**
| Step | Stage label | What becomes visible |
|------|-------------|----------------------|
| 1 | Detect | Incident header only |
| 2 | Collect | Evidence Explorer populated |
| 3 | Diagnose | DiagnosisPanel revealed |
| 4 | Approve | ApprovalCard in pending state |
| 5 | Remediate | Remediation executed state |
| 6 | Verify | VerificationCard with final outcome |

**Component structure to implement:**
```
ReplayMode
├── IncidentPicker      — dropdown populated from apiClient.getIncidents()
├── ReplayControls      — Play/Pause/Reset buttons, speed selector, stage progress bar
└── ReplayStageView     — renders frozen detail view for currentStage
    ├── Reuse LifecycleTimeline from IncidentDetail (pass frozen stage index as prop)
    ├── DiagnosisPanel    — hidden if currentStage < 3
    ├── EvidenceExplorer  — hidden if currentStage < 2
    ├── ApprovalCard      — hidden if currentStage < 4
    └── VerificationCard  — hidden if currentStage < 6
```

**Design rules (from `DESIGN_SPEC.md`):**
- Same Obsidian Command palette — black/graphite surfaces, no blue/purple/neon
- Use `bg-bg-surface`, `border-border-default`, `text-text-primary` etc. (all tokens are in `tailwind.config.js`)
- Pulsing amber dot on the currently active stage node (CSS `animate-pulse`)
- Play button: `btn-primary` style. Pause: `btn-ghost`. Reset: `btn-ghost`.
- Speed selector: `bg-bg-input border border-border-default rounded-button` select element
- No animations on page transitions — instant state changes only
- All data is fetched from `apiClient` in `src/config/api.js` — no direct `fetch()` calls

---

### Task 2 — Wire Approve/Reject in `ApprovalCard` (inside `IncidentDetail.jsx`)

Currently the buttons render but do nothing. The dashboard is read-only so use **Option A**:

Make the Approve button open the existing Phase 5 approval endpoint in a new tab:
```
https://0jqdaxn8k1.execute-api.ap-south-1.amazonaws.com/Prod/approval?incident_id=<id>&action=approve&token=<token>
```

- The `incident_id` is available from the incident object in context
- Omit the token param (the user will need their own) — just open the URL
- Add a `title` tooltip: `"Opens Phase 5 approval endpoint in a new tab"`
- The Reject button: same pattern with `action=reject`
- Add a small info note below the buttons: `"Approval is processed by the Phase 5 endpoint. This dashboard is read-only."` in `text-xs text-text-muted`

---

### Task 3 — Create `.env` files

Create `dashboard/web/.env`:
```
VITE_API_BASE_URL=https://0jqdaxn8k1.execute-api.ap-south-1.amazonaws.com/Prod
```

Create `dashboard/web/.env.example`:
```
# Base URL of the deployed dashboard API Gateway stage
VITE_API_BASE_URL=https://<api-id>.execute-api.<region>.amazonaws.com/Prod
```

Add `dashboard/web/.env` to the root `.gitignore` if not already present.

---

### Task 4 — Deploy and smoke test

From the `infra/` directory:
```bash
sam build
sam deploy
```

Then install and start the frontend:
```bash
cd dashboard/web
npm install
npm run dev
```

Verify:
1. `GET /incidents` returns real records from DynamoDB
2. `GET /incidents/<any_id>` returns `raw_data` from S3 alongside the record
3. The Overview feed loads incidents and polls every 5 seconds
4. Clicking an incident opens the 3-column detail view correctly
5. Analytics page renders without errors (charts may show empty states until evaluation harness has been run — that is expected)
6. ReplayMode loads the incident picker, stepping through all 6 stages works, Play/Pause/Reset all work correctly

---

## Key Files

```
PHASE8_HANDOFF.md                     ← Full inventory of what is already done
PROJECT_SPEC.md                       ← Steps 28–31 define Phase 8 requirements
DESIGN_SPEC.md                        ← Complete visual/component specification

src/dashboard/app.py                  ← Lambda API (read-only, already complete)
infra/template.yaml                   ← DashboardFunction + DashboardRole already added

dashboard/web/
├── package.json                      ← dependencies already defined
├── tailwind.config.js                ← Obsidian Command tokens already mapped
├── src/
│   ├── App.jsx                       ← router already has /replay route
│   ├── config/api.js                 ← use this for all API calls
│   ├── utils/constants.js            ← PIPELINE_STAGES, POLLING_INTERVALS, etc.
│   ├── utils/helpers.js              ← getIncidentStatus(), getPipelineStageStatus(), etc.
│   ├── components/Layout.jsx         ← already done
│   ├── components/IncidentFeed.jsx   ← already done
│   ├── pages/Overview.jsx            ← already done
│   ├── pages/IncidentDetail.jsx      ← done, needs ApprovalCard wired (Task 2)
│   ├── pages/Analytics.jsx           ← already done
│   └── pages/ReplayMode.jsx          ← MISSING — create this (Task 1)
```

---

## Constraints — Do Not Violate These

- **Dashboard is strictly read-only.** `DashboardRole` in `template.yaml` has no write permissions. Do not add any write API calls to the frontend or Lambda.
- **No OpenSearch / Bedrock Knowledge Bases.** Not relevant to Phase 8 but do not introduce them.
- **No new AWS services.** Reuse the existing API Gateway (`ServerlessRestApi`) already in `template.yaml`.
- **Do not touch Phases 0–7 Lambda code** (`src/collector`, `src/diagnosis`, `src/remediation`, `src/reporting`, `src/approval`, `src/verification`). Those are deployed and working.
- **Obsidian Command palette only.** No bright blue, purple, cyan, rainbow gradients, or neon anywhere in the UI. Check `DESIGN_SPEC.md` §2 if unsure.
- **No drop shadows on cards.** Elevation is achieved through border + surface colour contrast only (`DESIGN_SPEC.md` rule 1).
