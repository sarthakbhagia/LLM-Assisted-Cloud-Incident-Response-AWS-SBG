# Design Specification — LLM-Assisted Cloud Incident Response

**Status: Fully Implemented (Phase 8 Complete)** — All design tokens, components, and pages from this specification have been implemented in the `dashboard/web/` React application as of September 25, 2026.

This document is the complete design system and visual specification for the frontend application. It defines exactly how every UI element looks, feels, and behaves. For functional requirements, component data contracts, and API details, refer to the [Frontend Specification](FRONTEND_SPEC.md).

---

## 1. Product Identity

**Theme Name**: Obsidian Command
**Product Name**: Incident Command Center

The interface must feel like a serious, premium, production-grade cloud operations tool used by professional SREs under real incident pressure. It should not feel like a business analytics dashboard, a startup SaaS landing page, a colorful observability product, or a chatbot UI.

Design references:
- **Linear** — precision, density, clean dark surfaces, excellent typography.
- **Vercel Dashboard** — black and graphite, no decoration, clear data hierarchy.
- **Grafana** — information density, competent metrics display.
- **Modern security operation centers (SOCs)** — authoritative, calm, technical.

The product achieves this through black and graphite surfaces, restrained crimson accents for danger states, and precise off-white typography — nothing else.

---

## 2. Strict Color System

### 2.1 Color Discipline Rule
The interface must be **85–90% black, graphite, gray, and off-white**. The remaining 10–15% is semantic accent colors applied only to carry operational meaning.

Never use bright blue, purple, cyan, rainbow gradients, colorful card backgrounds, or neon glow. Violating this rule destroys the product identity.

### 2.2 The Obsidian Palette

**Surfaces (In Elevation Order)**
| Token | Hex | Usage |
| :--- | :--- | :--- |
| `--bg-base` | `#050505` | Full page background, root canvas |
| `--bg-sidebar` | `#0B0B0D` | Sidebar navigation |
| `--bg-surface` | `#111113` | Cards, panels, table rows |
| `--bg-elevated` | `#1B1B1F` | Hover states, selected rows, dropdowns |
| `--bg-input` | `#141416` | Input fields, search bars |

**Borders**
| Token | Hex | Usage |
| :--- | :--- | :--- |
| `--border-subtle` | `#1E1E22` | Innermost card dividers, row separators |
| `--border-default` | `#2A2A2D` | Card borders, panel edges |
| `--border-strong` | `#3A3A3E` | Active selection borders, focus rings |

**Typography**
| Token | Hex | Usage |
| :--- | :--- | :--- |
| `--text-primary` | `#F2F2F2` | All primary headings, values, critical labels |
| `--text-secondary` | `#85858C` | Supporting labels, metadata, secondary info |
| `--text-muted` | `#55555D` | Timestamps in non-critical context, empty states |
| `--text-inverted` | `#050505` | Text on colored badge backgrounds |

**Semantic Accents**

| Token | Hex | Usage — strict. Use only for the stated purpose. |
| :--- | :--- | :--- |
| `--crimson` | `#D63C4B` | Critical incidents, active incident count, critical severity badges, failed lifecycle stages, dangerous remediation warnings, the sidebar brand accent line |
| `--crimson-surface` | `#321419` | Background of critical banners and error blocks |
| `--amber` | `#F0A23A` | Pending approvals, awaiting-action stages, medium AI confidence badges |
| `--amber-surface` | `#2B2010` | Background of warning banners |
| `--emerald` | `#46B887` | Healthy services, successful remediations, verified/resolved states, high AI confidence badges |
| `--emerald-surface` | `#0E2420` | Background of success banners |

### 2.3 What Crimson Is Not Used For
Crimson is the brand accent. It is **not** a generic highlight color.

- Not used for link hovers.
- Not used for active tabs.
- Not used for focus rings (use `--border-strong`).
- Not used for non-critical text highlights.
- Not used as a background across large surface areas.

---

## 3. Typography

**Font Family**: `Inter` (loaded from Google Fonts). Fallback: `system-ui, sans-serif`.
**Monospace Font**: `JetBrains Mono` or `Fira Code`. Used for incident IDs, timestamps, JSON, log lines, and code blocks.

### 3.1 Type Scale

| Role | Size | Weight | Line Height | Color |
| :--- | :--- | :--- | :--- | :--- |
| Page title | 20px | 600 | 1.3 | `--text-primary` |
| Section heading | 15px | 600 | 1.4 | `--text-primary` |
| Card heading | 13px | 500 | 1.4 | `--text-primary` |
| Body | 13px | 400 | 1.6 | `--text-primary` |
| Caption | 11px | 400 | 1.5 | `--text-secondary` |
| Monospaced label | 12px | 400 | 1.5 | `--text-secondary` |
| Monospaced code | 12px | 400 | 1.6 | `#A8C5DA` (subtle blue-white for code) |
| Badge text | 11px | 500 | 1 | varies by badge |

---

## 4. Spacing & Layout System

### 4.1 Spacing Scale (Base: 4px)
All spacing uses multiples of 4px.

| Token | Value |
| :--- | :--- |
| `space-1` | 4px |
| `space-2` | 8px |
| `space-3` | 12px |
| `space-4` | 16px |
| `space-5` | 20px |
| `space-6` | 24px |
| `space-8` | 32px |
| `space-10` | 40px |
| `space-12` | 48px |

### 4.2 Border Radius
| Element | Radius |
| :--- | :--- |
| Cards / Panels | `6px` |
| Badges | `4px` |
| Buttons | `5px` |
| Input fields | `5px` |
| Confirmation modals | `8px` |
| Tooltips | `4px` |

**No pill-shaped buttons or rounded-full badges for operational elements.** They read as playful and consumer. Use tight, precise radii.

### 4.3 Application Layout

**Desktop (1440px)**:
```
[ Sidebar 220px fixed ] [ Main content area 1220px ]
```

**Sidebar**: Fixed, never collapsed by default. Can be toggled to 56px icon-only mode via a keyboard shortcut or chevron icon.

**Header**: Fixed top bar, 48px tall, inside the main content area.

**Page Container**: `padding: 24px`. Max content width: `1120px`. Centered within the main content area.

**Responsive Breakpoints**:
| Breakpoint | Width | Layout change |
| :--- | :--- | :--- |
| xl | 1280px | Full layout as described |
| lg | 1024px | Sidebar collapses to 56px icon-only |
| md | 768px | Sidebar hidden (drawer), single column |
| sm | 640px | Sidebar drawer, stacked full-width panels |

---

## 5. Component Design System

### 5.1 Sidebar

- Background: `--bg-sidebar` (`#0B0B0D`)
- Top: 16px padding — abstract minimal cloud shield logo (single-color white SVG, 28px) + "Incident Command Center" in 13px weight-500 primary text.
- Nav items: 36px tall, 12px horizontal padding, 13px body text.
  - Default: `--text-secondary` text.
  - Hover: `--bg-elevated` background.
  - Active: `--bg-elevated` background + 2px solid `--crimson` left border inset. Text `--text-primary`.
- Bottom: Small environment selector and user avatar, separated by a `--border-default` divider.

### 5.2 Header

- Background: `--bg-base` with a 1px `--border-subtle` bottom border.
- Height: 48px.
- Left: Current page title in 15px weight-600.
- Center: Nothing (keep it clear).
- Right: Environment pill selector (dev / staging / prod) → notification bell icon → "Last updated N seconds ago" timestamp tag → user avatar.

### 5.3 Cards & Panels

All cards:
- Background: `--bg-surface` (`#111113`)
- Border: 1px solid `--border-default`
- Border radius: 6px
- Padding: 16px (inner content), 24px top/bottom for taller informational panels.
- No drop shadows. Elevation is created by the contrast between `--bg-base` and `--bg-surface`, supported by the border.

### 5.4 Badges

Badges are compact, rectangular with 4px radius. All text is 11px weight-500.

**Severity Badges**:
| Label | Background | Text |
| :--- | :--- | :--- |
| Critical | `--crimson-surface` | `--crimson` |
| Warning | `--amber-surface` | `--amber` |
| Info | `#1A1A1E` | `--text-secondary` |

**Status Badges** (pipeline stage):
| Label | Background | Text |
| :--- | :--- | :--- |
| Detected | `#1A1A1E` | `--text-secondary` |
| Diagnosing | `#1A1A20` | `#7C7CFF` (subtle neutral purple, AI-associated) |
| Pending Approval | `--amber-surface` | `--amber` |
| Approved | `#0E2420` | `--emerald` |
| Executed | `#0E2420` | `--emerald` |
| Resolved | `--emerald-surface` | `--emerald` |
| Not Resolved | `--crimson-surface` | `--crimson` |
| Failed | `--crimson-surface` | `--crimson` |
| Rejected | `#1A1A1E` | `--text-muted` |

**Confidence Badges** (AI Diagnosis):
| Range | Background | Text | Label |
| :--- | :--- | :--- | :--- |
| 90–100% | `--emerald-surface` | `--emerald` | High |
| 70–89% | `--amber-surface` | `--amber` | Medium |
| <70% | `--crimson-surface` | `--crimson` | Low — review carefully |

### 5.5 Buttons

**Primary / Confirm Action** (low-risk):
- Background: `#1B1B1F`, border: `--border-strong`, text: `--text-primary`.
- Hover: `#222226`, border: `#4A4A4E`.
- 13px, weight-500, 5px radius, 28px height.

**Danger Action** (approve high-risk remediation):
- Background: `--crimson-surface`, border: `1px solid #7A1E27`, text: `--crimson`.
- Hover: Increase border opacity slightly.
- Requires a ConfirmDialog before invoking the API.

**Ghost / Secondary** (reject, cancel):
- No background, border: `--border-default`, text: `--text-secondary`.
- Hover: `--bg-elevated` background.

**Destructive Link** (rarely used):
- No background, no border, text: `--crimson`.
- For inline contextual danger (e.g., "Clear all incidents" in dev environment).

**Disabled state** for all buttons:
- Opacity: 40%. Cursor: `not-allowed`. Never hidden.

### 5.6 Tables

- Background: `--bg-surface`
- Header row: `--bg-elevated`, text: `--text-secondary` 11px uppercase weight-500 with 1px letter-spacing.
- Data rows: 40px height, `--text-primary` 13px, bottom border `--border-subtle`.
- Hover: `--bg-elevated` background.
- Selected: `--bg-elevated` + 1px `--border-strong` left inset.
- Sortable column headers: include a small chevron icon, color changes to `--text-primary` on active sort.
- No zebra striping.

### 5.7 Incident Lifecycle Timeline (Vertical Stepper)

Each stage is a row with:
- Left: A 20x20 status icon node
  - Complete: Solid `--emerald` circle with white check icon
  - In Progress: Amber circle, pulsing CSS animation at 1.5s period
  - Awaiting: Hollow circle, `--border-default` stroke
  - Failed: Solid `--crimson` circle with white cross icon
  - Not Started: Dashed `--border-subtle` circle
- Vertical connector line between nodes: `--border-subtle`, 1px, dashed if below a "Not Started" node.
- Right of icon: Stage name (13px weight-500) on line 1. Timestamp (11px monospaced `--text-muted`) on line 2. Metadata (11px `--text-secondary`) on line 3.
- Clicking an active or complete stage expands an inline sub-card (`--bg-elevated`, 6px radius, 12px padding) showing input/output summary.

### 5.8 Code & Log Viewer

Background: `#080809` (slightly different from `--bg-base` to create a terminal inset feel).
Font: `JetBrains Mono`, 12px, line height 1.6.
Border: 1px `--border-subtle`, 6px radius.

Log-level colorization:
- `ERROR`: `#D63C4B` (crimson)
- `WARN`: `#F0A23A` (amber)
- `INFO`: `#85858C` (secondary gray)
- `DEBUG`: `#55555D` (muted)

JSON syntax highlighting:
- Keys: `#A8C5DA`
- String values: `#7ABF8C`
- Number values: `#D4A574`
- Boolean/null: `#C792EA`

### 5.9 Metric Charts (Recharts)

- Chart background: transparent (inherits card surface).
- Grid lines: `--border-subtle`, dotted, horizontal only.
- Axis labels: 11px `--text-muted`, monospaced.
- Data line: 1.5px stroke, `--text-primary` (`#F2F2F2`) for the primary metric.
- Alarm threshold line: 1px dashed `--crimson` with a small inline label "Alarm threshold".
- Tooltips: `--bg-elevated` background, 1px `--border-default` border, 6px radius, 12px padding.
- No fill-area gradients on the primary metric line. Keep it clean and precise.
- Legend: Bottom of chart, 11px `--text-secondary`.

### 5.10 Empty States

- Centered in the panel with `32px` vertical padding.
- Icon: 32px Lucide icon, `--text-muted` color.
- Heading: 13px weight-500 `--text-secondary`.
- Sub-text: 12px `--text-muted`.
- Action button (if applicable): Ghost style.

Examples:
- Incidents List empty: "No incidents match your filters." + "Clear filters" button.
- Overview empty (no active): "No active incidents. Your cloud environment is healthy."
- Verification empty: "Verification has not run yet."

### 5.11 Skeleton Loaders

Use CSS pulse animation (opacity 0.5 to 1.0, 1.5s ease-in-out, infinite).
- Color: `--bg-elevated`
- Shape: Matches the content shape it is replacing. A table skeleton shows row-shaped bars. A KPI card skeleton shows a small number-shaped block and a label-shaped block.
- Border radius: matches the content it replaces.

### 5.12 Confirmation Dialogs

Modal overlay: `rgba(0,0,0,0.7)` backdrop, blur `4px`.
Dialog panel: `--bg-surface`, 1px `--border-default`, 8px radius, max-width `480px`, centered.

Contents:
- Title: 15px weight-600 `--text-primary`.
- Body: 13px `--text-secondary` with specific action details.
- For dangerous actions: A red banner inside the dialog: "You are about to modify production infrastructure. This action cannot be automatically reversed." in `--crimson` text on `--crimson-surface` background.
- Buttons: Cancel (ghost) + Confirm (Danger button), right-aligned.

---

## 6. Design System Rules

These rules must be followed consistently across all six pages to maintain visual cohesion.

1. **Surface elevation is achieved through border + color contrast, not shadows.** Never add `box-shadow` to cards.
2. **Crimson is a danger signal, not a brand highlight.** Only use it when something requires urgent attention or when marking a critical state.
3. **Every AI-generated value is visually grounded.** The AI diagnosis panel must look like a data component, not an assistant chat bubble. No rounded "chat" styling on AI content.
4. **Tables over cards for lists.** When displaying more than 3 incidents, use a table with rows, not a grid of cards.
5. **Monospaced font for technical identifiers.** Incident IDs, timestamps, Lambda names, S3 keys, and metric names must all use `JetBrains Mono`.
6. **Never hide information behind an unexplained icon.** Every icon that carries meaning must have a tooltip or visible label.
7. **Approve and Reject must not look similar.** The danger/ghost button contrast must be strong enough that they cannot be confused.
8. **Loading, empty, and error states are mandatory.** No data-dependent component ships without all three states implemented.
9. **The AI confidence score must show its label.** Never show a bare percentage without a "High / Medium / Low" label and the corresponding color badge.
10. **Verification state is not the same as remediation success.** These must be rendered as two distinct components that are never merged or confused.

---

## 7. Page-by-Page Layout Specification

### 7.1 Overview Dashboard

```
┌─ Header (48px) ────────────────────────────────────────────────────────────┐
│  Overview                                       Production  •  Live  [user] │
└────────────────────────────────────────────────────────────────────────────┘
┌─ KPI Row (4 cards, equal width, 16px gap) ─────────────────────────────────┐
│  [Active Incidents]  [Pending Approvals]  [Recovery Success]  [MTTR]        │
└────────────────────────────────────────────────────────────────────────────┘
┌─ Main Content ──────────────────────────────────────┐ ┌─ Right Panel ──────┐
│  Active Incidents table (takes 70% width)           │ │ System Health      │
│  Full-width table, sortable, with action shortcuts  │ │                    │
│                                                     │ │ Recent Remediations│
└─────────────────────────────────────────────────────┘ └────────────────────┘
```

### 7.2 Incident Detail

```
┌─ Incident Header (full width, 80px) ───────────────────────────────────────┐
│  [Critical] INC-1042  Service A — High Lambda Duration  [Pending Approval]  │
│  Detected 3 min ago  •  Source: CloudWatch  •  Production                   │
└────────────────────────────────────────────────────────────────────────────┘
┌─ Left (30%) ────────┐ ┌─ Center (45%) ──────────────┐ ┌─ Right (25%) ─────┐
│                     │ │                              │ │                   │
│  Lifecycle Timeline │ │  AI Diagnosis Panel          │ │  Approval Card    │
│                     │ │                              │ │                   │
│  [Detect] ✓         │ │  [Root Cause]                │ │  [Pre-flight]     │
│  [Collect] ✓        │ │  [Confidence 94% High]       │ │  [Approve]        │
│  [Diagnose] ✓       │ │  [Runbook: used]             │ │  [Reject]         │
│  [Approve] ●        │ │  [Suggested: scale_up]       │ │                   │
│  [Remediate] ○      │ │  [Reasoning trace ▾]         │ ├───────────────────┤
│  [Verify] ○         │ ├──────────────────────────────┤ │  Verification     │
│                     │ │  Evidence Explorer           │ │  (when available) │
│                     │ │  [Metrics][Logs][Xray][JSON] │ │                   │
└─────────────────────┘ └──────────────────────────────┘ └───────────────────┘
```

### 7.3 Analytics

```
┌─ KPI Row (4 cards) ────────────────────────────────────────────────────────┐
│  [MTTR]  [Diagnosis Success]  [Verification Success]  [D-R Gap %]           │
└────────────────────────────────────────────────────────────────────────────┘
┌─ Row 2 (2 charts, 50/50) ──────────────────────────────────────────────────┐
│  Incident Timeline (bar chart)        │  MTTR Distribution (histogram)      │
└────────────────────────────────────────────────────────────────────────────┘
┌─ Row 3 (2 charts, 50/50) ──────────────────────────────────────────────────┐
│  Confidence vs Correctness (scatter)  │  Diagnosis-Recovery Gap (bar)       │
└────────────────────────────────────────────────────────────────────────────┘
┌─ Row 4 (2 charts, 50/50) ──────────────────────────────────────────────────┐
│  Failure Mode Taxonomy (stacked bar)  │  RAG vs No-RAG (side-by-side bars)  │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Animation & Interaction

- **Page transitions**: Instant. No slide or fade animations between pages. Speed is critical in a command center.
- **Component data refresh**: Values update in place. If a KPI value changes, briefly flash the text to `--text-primary` at 120% opacity, then fade back. Duration: 300ms ease-out.
- **Pulsing status indicators**: Use CSS animation `opacity: 1 -> 0.4 -> 1` at 1.5s period for "In Progress" lifecycle stages.
- **Table row hover**: `background-color` transition 80ms ease.
- **Approval confirm dialog**: Fade in `0.15s ease`. Backdrop fade in `0.15s`.
- **Skeleton loaders**: Pulse animation `1.5s ease-in-out infinite`.
- **Sidebar active state**: No animation. Instant state change. Crimson border is static, not animated.

No bouncing, spinning, floating, or attention-seeking animations anywhere in the interface. Every animation must serve a functional purpose (status indication, data freshness, focus guidance).
