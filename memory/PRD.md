# Life Blueprint — Product Requirements

## Original problem statement
Motivational + life-events app for the next 40 years of a 40-year-old. Fitness (customizable workouts, healthy recipes), self-love / motivation / meditation (podcasts, meditations, real-life stories), personal dates + events + reminders. Single-user local app. AI: Claude Sonnet 4.5. Design: warm, calm, earthy. Final form: native Android app via Capacitor.

## Architecture (current — Feb 2026)
```
Android APK (Capacitor WebView) ──► loads ──► Vercel (React frontend)
                                                    │
                                                    └──► API ──► Railway (FastAPI backend)
                                                                    │
                                                                    └──► MongoDB Atlas (free M0)
```
- APK: Capacitor 6 wrapper. Loads `https://life-5m18.vercel.app` via `server.url`.
- Frontend: Vercel, auto-deploys on every GitHub push. Env: `REACT_APP_BACKEND_URL`.
- Backend: Railway, auto-deploys on every GitHub push. Env: `MONGO_URL`, `DB_NAME`, `EMERGENT_LLM_KEY`, `JWT_SECRET`, `AUTH_EMAIL`, `AUTH_PASSWORD`.
- DB: MongoDB Atlas — personal account, free M0 cluster, user `qasim3638_db_user`. **Password rotation needed** (was exposed in chat).
- Android URL: repo `qasim3638/Life`, local clone at `~/Life`.

## Implemented (through Feb 2026)
- Full life-planning feature set: Today/Tomorrow, Blueprint, Fitness, Recipes, Self, Focus, Sobriety, Family, Companion, Motivation, Meditate, Self-Care, Events, Review, Sanctuary
- Companion "Yaar" with persistent multi-turn memory, PIN gate (4242), memory lane search
- Today Plan card with priorities/chores/inline Ask Yaar
- Voice: Whisper STT, OpenAI TTS (`coral`), Voice Briefs (morning/midday/evening) with Capacitor LocalNotifications
- Sanctuary immersive player
- Capacitor Android wrapper, custom moss-green "Lb" icon + cream splash
- Cloud deploy: Railway backend + MongoDB Atlas + Vercel frontend (Feb 2026)
- **JWT auth / lock screen** (Feb 2026) — `/api/auth/login`, `/api/auth/me`, bearer-token middleware on all `/api/*` routes (except `/api/`, `/api/auth/*`, `/api/uploads/*`). 30-day tokens. 5-fail 15-min brute force lockout. AuthGate component wraps full app. Middleware is env-gated — no `AUTH_EMAIL`/`AUTH_PASSWORD` means auth disabled (dev mode).

## Active blockers
- None code-wise — awaiting user to:
  1. Save latest commit to GitHub (auth code)
  2. Add `JWT_SECRET`, `AUTH_EMAIL`, `AUTH_PASSWORD` env vars on Railway
  3. Test lock screen on phone

## Roadmap (priority order)

### P1 — Hands-free Yaar (user requested, next session)
- **Level 3**: Custom "Hey Yaar" wake word using Picovoice Porcupine + Android foreground service (2-3 sessions)
- **Level 1**: Shake-to-talk gesture (quick add once Level 3 voice pipeline exists)
- **Level 2**: Google Assistant App Actions ("Hey Google, ask Yaar...")

### P2 — Hygiene
- Rotate MongoDB Atlas password (was exposed in chat — user to do)
- `DialogDescription` a11y prop on all shadcn Dialogs
- Drag-to-rearrange time blocks on Tomorrow page

### P3 — Future
- Live Reload for Capacitor (changes on phone without APK rebuild)
- iOS build (requires Mac)

## Test credentials
See `/app/memory/test_credentials.md`.

## Docs
- `/app/memory/RAILWAY_DEPLOY.md` — Railway + MongoDB Atlas deploy guide
- `/app/memory/MOBILE_SETUP.md` — Android Studio build instructions (now stale after Vercel+Railway switch)
- `/app/memory/test_credentials.md` — auth credentials reference
