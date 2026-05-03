# Life Blueprint — PRD

## Original Problem Statement
Build a motivational/life-planning app to help a 40-year-old shape the next 40 years:
fitness (customizable workouts), healthy recipes (Pakistani/Indian/Arab, low-carb high-protein, no pork/bacon),
self-love & self-care, motivational podcasts/speeches/quotes, meditations, personal dates/events/reminders,
and anything that helps build a routine for staying healthy, happy and fit.

## User Choices
- AI via **Claude Sonnet 4.5** (Emergent LLM key)
- **No auth** — single-user local app
- Motivation = curated quotes + YouTube embeds
- In-app reminders only
- Design vibe: **Warm & calm** — Cormorant Garamond + Manrope, #FDFBF7 / #59745D moss / #C27A62 terracotta / #A3897C clay / #E8E2D2 sand

## Architecture
- Backend: FastAPI + MongoDB (Motor), modular routes under `/app/backend/routes/`
  (`workouts, recipes, journal, events, life_goals, content, day_plans, streaks, ai_endpoints, companion, family, audio, self_profile, focus, sobriety, echo, sunday_review, uploads`)
- Static files served at `/api/uploads/*` from `/app/backend/uploads/`
- AI: `emergentintegrations` → Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`)
- Frontend: React + shadcn/ui + Tailwind. Pages in `/app/frontend/src/pages/`, shared card components under `/app/frontend/src/components/{today,companion}/`.

## Features Shipped
1. **Today** – life-arc ring, AI wisdom, quote, echo-of-yesterday, protected (sober+focus) card, daily AI brief, streak protector (after 6pm), Sunday banner, weekly letter. Cards extracted into `/components/today/*` for maintainability.
2. **Tomorrow** – time-blocked schedule, morning routine, meals, supplements, chores
3. **Blueprint** – 40-year goals + jsPDF export
4. **Fitness** – workout builder, logs, AI coach
5. **Recipes** – 12 seeded halal low-carb high-protein recipes, filters, AI chef, **file-upload OR URL-paste for recipe images** (stored in `/app/backend/uploads/`, max 5MB, .jpg/.jpeg/.png/.webp/.gif)
6. **Motivation** – quotes + YouTube podcasts/speeches
7. **Meditate** – breath timer + global sticky audio player (meditation music, sleep stories, wisdom stories)
8. **Self-Care** – mood, gratitude, journal, affirmations, AI coach
9. **Events** – shadcn Calendar, recurring dates/reminders
10. **Self Profile** – appearance/personality/mind/style/gear + AI Daily Brief
11. **Focus** – Pomodoro sessions + distraction logging, tz-aware stats
12. **Sobriety** – multi-addiction tracker, clean streak, slip logging
13. **Family** – timeline of memories + holidays, edit/delete
14. **Companion** – AI friend with auto-memory extraction, pinning, TTL. Sidebar/dialogs extracted into `/components/companion/*`.
15. **Sunday Rhythm Review** – weekly AI reflection pulled from workouts/journal/focus/slips/family/plan data. Featured card + past reviews with 5 stat tiles. Sunday-only banner on Today dashboard.

## Changelog
- 2026-02: Sunday Rhythm Review frontend (Review.jsx + nav + Today banner). 102/102 backend tests + frontend E2E pass.
- 2026-02: Recipe image upload endpoint + file-picker/URL UI. Today.jsx refactored into 5 cards (316 lines, was 461). Companion.jsx refactored into 3 extracted components. 100% backend + frontend tests.

## Prioritized Backlog
- **P2** A11y: add `aria-describedby` / DialogDescription to all shadcn Dialogs (non-blocking warning surfaced by testing agent)
- **P3** Drag-to-rearrange time blocks on Tomorrow page
- **P3** Emailable weekly-review keepsake / year-in-review compile
