# KaamSetu — Daily Workforce Dispatch & Operations Platform

KaamSetu (*Bridge to Work*) is a real-time daily workforce dispatch platform built for India's unorganized daily-wage market. It connects households and local businesses directly with verified daily-wage workers (painters, plumbers, cleaners, cooks, electricians, gardeners) for immediate daily jobs.

---

## The Problem & What KaamSetu Solves

### The Problem
Finding reliable daily help for short 1-day tasks (e.g. painting a living room, deep kitchen cleaning, tap repair) in Indian cities remains fragmented:
* **For Households**: Unreliable word-of-mouth recommendations, zero background verification, and arbitrary daily pricing.
* **For Workers**: Unpredictable daily work, middleman commission cuts (up to 30%), and no permanent record or reputation history.

### The Solution
KaamSetu digitizes daily labor dispatch into a clean, mobile-first experience:
1. **60-Second Dispatch**: Households create a daily job posting with task requirements and daily rates. Nearby verified workers receive notifications instantly.
2. **Dual-Mode Architecture**: Users can switch seamlessly between **Employer Mode** (posting jobs) and **Worker Mode** (finding daily work) inside the exact same app session with a single tap.
3. **Direct Connection & Verification**: Worker profiles display Aadhaar verification badges and skill tags. Phone numbers unlock once a worker is assigned to a job.
4. **Transparent Rates**: Jobs list upfront daily pay rates with zero middleman deductions.

---

## What's Built in the Repo Today

* **Product Landing Screen**: Single-line logo lockup in the top navigation bar, product headline, live trust metrics, and direct entry points to Employer and Worker feeds.
* **OTP Mobile Authentication**: Phone number authentication screen with 6-digit verification code input, countdown resend timers, and toast alert feedback.
* **Dual-Mode Dashboard**:
  * *Employer Mode*: Service marketplace category grid, overview of active postings, category distribution, and job dispatch triggers.
  * *Worker Mode*: Availability status, current sector radius, and expected daily wage rate settings.
* **Job Dispatch Ledger**: Full-screen job search with real-time text query filtering, modal category selector (`AppBottomSheet`), and tabbed status management (`OPEN`, `ASSIGNED`, `COMPLETED`).
* **4-Stage Job Stepper**: Visual progress tracker (`Posted` → `Interested` → `Assigned` → `Completed`) with task specs, applicant worker cards, and sticky bottom action bar.
* **System Profile & Skills Management**: Worker profile editor to toggle availability (`available` / `busy`), customize skill badges via slide-up sheet, view ratings, and access compliance records.
* **Light Theme Design System**: Custom Flutter design tokens (`AppColors.canvas`, `AppColors.surface`, `AppColors.brand`) with strict single-accent color discipline (`#D97706` amber reserved for primary CTAs, active states, and prices).

---

## Tech Stack

| Layer | Library / Tool | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Framework** | Flutter | `^3.24.0` | Cross-platform native mobile application engine |
| **Language** | Dart | `^3.5.0` | Strongly-typed OOP language for UI and logic |
| **State Management** | Flutter Riverpod | `^2.6.1` | Reactive, compile-safe state management |
| **Navigation** | GoRouter | `^14.8.0` | Declarative URL-friendly routing with `ShellRoute` |
| **Typography** | Google Fonts | `^6.2.1` | Sora (headlines/titles) & Inter (body text) |
| **Animations** | Flutter Animate | `^4.5.2` | Fluid micro-interactions & press scale feedback |
| **Database & Auth** | Supabase Flutter Client | `^2.8.0` | PostgreSQL client with Row Level Security (RLS) |

---

## System Architecture

```mermaid
   graph TD
    %% User Devices / Platforms
    subgraph Platforms["1. Cross-Platform Frontend (Flutter & Dart)"]
        A[Android App]
        B[iOS App]
        C[Web Application]
    end

    %% UI & Navigation Layer
    subgraph UI_Layer["2. Presentation Layer"]
        DS["Tokenized Design System<br/>(Colors, Typography, Spacing)"]
        GR["GoRouter + ShellRoute<br/>(Persistent Bottom Nav & Mode Switcher)"]
        
        EM["Employer Mode Screens<br/>(Post Jobs, View Applicants)"]
        WM["Worker Mode Screens<br/>(Find Jobs, Manage Applications)"]
    end

    %% State Management Layer
    subgraph State_Layer["3. State Management (Riverpod)"]
        RP["Riverpod State Providers"]
        AuthProv["Auth State Provider"]
        JobProv["Job Data Provider"]
        ModeProv["App Mode Provider<br/>(Employer / Worker)"]
    end

    %% Backend Services (Supabase)
    subgraph Backend["4. Backend & Database (Supabase)"]
        S_Auth["Supabase Auth"]
        S_API["Supabase REST / Realtime API"]
        
        subgraph Postgres["PostgreSQL Database"]
            RLS["Row Level Security (RLS) Layer"]
            DB_Jobs[("Jobs & Assignments Table")]
            DB_Users[("Users & Worker Profiles Table")]
        end
    end

    %% Connections
    Platforms --> DS
    DS --> GR
    GR --> EM
    GR --> WM

    EM --> RP
    WM --> RP

    RP --> AuthProv
    RP --> JobProv
    RP --> ModeProv

    AuthProv --> S_Auth
    JobProv --> S_API

    S_Auth --> RLS
    S_API --> RLS

    RLS --> DB_Jobs
    RLS --> DB_Users

    %% Styling / Aesthetics
    classDef frontend fill:#02569B,stroke:#0175C2,color:#FFFFFF;
    classDef router fill:#13B9FD,stroke:#0175C2,color:#000000;
    classDef state fill:#42A5F5,stroke:#1E88E5,color:#FFFFFF;
    classDef backend fill:#3ECF8E,stroke:#24B47E,color:#000000;
    classDef db fill:#2496ED,stroke:#000000,color:#FFFFFF;

    class A,B,C frontend;
    class GR,DS router;
    class RP,AuthProv,JobProv,ModeProv state;
    class S_Auth,S_API backend;
    class RLS,DB_Jobs,DB_Users db;
```

## Project Structure

```
Tech-Rush-MVP/
├── assets/                     # Static image assets & app icons
│   └── images/                 # KaamSetu painter mascot logos
├── android/                    # Native Android Gradle configuration
├── ios/                        # Native iOS Xcode workspace & Runner app
├── lib/                        # Core Flutter application source code
│   ├── main.dart               # App entry point & ProviderScope setup
│   ├── core/                   # Design system tokens, theme, formatters, spacing
│   ├── models/                 # Strongly-typed Dart data models (Job, Worker, etc.)
│   ├── routing/                # GoRouter route declarations & ShellRoute
│   ├── screens/                # Modular UI screens (Splash, Auth, Dashboard, Jobs, Profile)
│   ├── services/               # Supabase client service & backend integrations
│   └── widgets/                # Reusable UI widgets (ServiceCard, StatusChip, Logo, etc.)
├── test/                       # Flutter unit & widget tests
└── pubspec.yaml                # Flutter project dependencies & asset definitions
```
