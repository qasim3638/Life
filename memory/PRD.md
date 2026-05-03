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
- 2026-02: Upload endpoint now auto-compresses to WebP — full-size (longest edge ≤ 1600px, q85) + 400×300 thumbnail (q75). Recipe model gained `thumb` field; card grid uses thumbnail, detail modal keeps full. 2400×1600 JPEG (60KB) → 3KB WebP + 300-byte thumb (~20× smaller).
- 2026-02: Recipe cards now use native `<img>` with `loading="lazy"`, `decoding="async"`, and fixed `width=400 height=300` (modal: 800×448) for zero-CLS, smooth scrolling at any catalog size.
- 2026-02: AI macro estimation — `POST /api/ai/recipe-macros` uses Claude Sonnet 4.5 to estimate prep time + calories + protein/carbs/fat per serving from the ingredient list. New "Estimate macros" button in the Add Recipe dialog pre-fills all five numeric fields. Backend + frontend tests 100%.
- 2026-02: YouTube library curation — `POST/DELETE /api/podcasts` and `/api/meditations` accept any YouTube URL form (watch?v=, youtu.be, /embed/, /shorts/, or raw 11-char ID), extract the ID server-side via regex, and store as `is_custom: true`. Motivation + Meditate pages have an "Add your own" dialog. Seeded items are protected from deletion (404 returned). Resilient UI: `<YouTubeThumb>` auto-detects YouTube's 120×90 broken-video placeholder and swaps in a warm fallback card; every card carries a "Watch on YouTube ↗" escape-hatch link. Fixed 5 dead seeded IDs (Jordan Peterson, Goggins, Eckhart Tolle, Rumi, Walking Meditation) in seed file + live DB.
- 2026-02: Removed "Made with Emergent" badge from `public/index.html`.
- 2026-02: Shuffle / "Try another" — per-card shuffle button on every Motivation podcast and Meditate audio card cycles that slot to a random other video from the library.
- 2026-02: Library expansion — 8→17 podcasts, 6→15 meditations, 15→40 quotes. All YouTube IDs HTTP-verified.
- 2026-02: "Fresh batch" quote refresh button — displays 6 random quotes at a time; rotates to a new random sextet on click (respects active category filter).

## Prioritized Backlog
- **P2** A11y: add `aria-describedby` / DialogDescription to all shadcn Dialogs (non-blocking warning surfaced by testing agent)
- **P3** Drag-to-rearrange time blocks on Tomorrow page
- **P3** Emailable weekly-review keepsake / year-in-review compile
