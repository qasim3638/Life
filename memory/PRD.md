# Life Blueprint — PRD

## Original Problem Statement
Build a motivational/life-planning app to help a 40-year-old shape the next 40 years:
fitness (customizable workouts), healthy recipes (Pakistani/Indian/Arab, low-carb high-protein, no pork/bacon),
self-love & self-care, motivational podcasts/speeches/quotes, meditations, personal dates/events/reminders,
and anything that helps build a routine for staying healthy, happy and fit.

## User Choices (from first ask_human)
- AI features via **Claude Sonnet 4.5** (Emergent LLM key)
- **No auth** — single-user local app
- Motivation = **curated quotes + YouTube embeds**
- **In-app reminders only**
- Design vibe: **Warm & calm** (earthy tones, serene)

## Architecture
- Backend: FastAPI + MongoDB (Motor) — `/app/backend/server.py`
- AI: `emergentintegrations` → Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`)
- Frontend: React + shadcn/ui + Tailwind — `/app/frontend/src`
- Fonts: Cormorant Garamond (serif) + Manrope (body)
- Palette: #FDFBF7 base, #59745D moss-green, #C27A62 terracotta, #A3897C clay, #E8E2D2 sand

## Feature Areas Implemented (2026-02)
1. **Today (Dashboard)** – life-arc progress ring (40 yrs ahead), AI "wisdom for today", daily quote, stats bento, upcoming events
2. **Blueprint** – 40-year life goals plotted by 5-year age brackets (40–80), category-tagged, status cycling (planted → tending → bloomed)
3. **Fitness** – workout builder (exercises/sets/reps/rest), workout CRUD, logging, AI coach suggestion
4. **Recipes** – 12 seeded halal low-carb high-protein recipes (Pakistani/Indian/Arab/Mediterranean) with macros, search + cuisine/meal filters, detail modal, AI chef
5. **Motivation** – 15 curated quotes (filterable by category) + 8 YouTube podcast/speech embeds
6. **Meditate** – breath-ring timer (5/10/15/20 min presets) + 6 guided YouTube sessions
7. **Self-Care** – daily mood, 3-gratitude, reflection journal, 8 affirmations, AI compassionate coach reflection
8. **Events** – shadcn Calendar with event markers, add birthdays/anniversaries/goals/reminders (recurring option)

## What Works
- All 18 backend tests pass (recipes, quotes, podcasts, meditations, affirmations, workouts CRUD + logs, journal, events, life-goals, 4 AI endpoints)
- No MongoDB `_id` leaks, no pork/bacon in recipes or AI output
- Claude Sonnet 4.5 responses flowing through for motivation/reflection/meal/workout

## Prioritized Backlog
- **P1** Sound for meditation breath timer (bell on complete)
- **P1** Export/PDF the 40-year blueprint as a keepsake
- **P1** Replace `@app.on_event` with FastAPI `lifespan` (tech debt)
- **P2** Streaks / habit tracker (daily workout + journal streaks)
- **P2** Push (or email) reminders for upcoming events
- **P2** Image upload for custom recipes
- **P2** Weekly AI-written "letter to future me" summary
