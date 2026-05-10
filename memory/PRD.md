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
- **JWT auth / lock screen** (Feb 2026) — `/api/auth/login`, `/api/auth/me`, bearer-token middleware. AuthGate wraps full app. Env-gated.
- **Hands-free Phase A** (Feb 2026) — "Hi Yaar" wake word + Shake-to-talk + Eagle voiceprint. WakeSettings dialog. Foreground only.
- **Yaar Whisper Mode** (Feb 2026) — `/reminders` page, backend `/api/reminders/*`, WhisperEngine polls + summons gently with chime + name. Configurable summon style/name/gap/max/fallback. Per-reminder overrides. Acknowledged via tap or wake word.
- **Phase B native scaffold** (Feb 2026) — `HandsFreeService.kt` foreground service, `HandsFreePlugin.kt` Capacitor plugin, AndroidManifest + Gradle deps for Picovoice Android SDKs. JS bridge `handsFreeBridge.js` auto-copies models from web to filesDir. Always-on toggle in Settings. **Code committed but UNTESTED — needs user Android Studio rebuild + iteration**.
- **Voice Note → Journal** (Feb 9, 2026) — New `VoiceNoteToText.jsx` inline mic button on Self-Care reflection. Tap → record (max 60s with countdown) → tap → Whisper transcribe → text appended to textarea. User reviews/edits → "Keep this" saves as journal entry. **TESTED & WORKING in production (Vercel + Railway, May 9 2026 user confirmation).**
- **Backend diagnostic endpoint** (Feb 9, 2026) — `/api/auth/_diag` returns env-var presence + Mongo ping (booleans only, no values).
- **Capacitor APK native build** (May 10, 2026) — User successfully built + installed Life Blueprint APK on S24 Ultra after extensive Gradle/JDK debugging (Kotlin 1.9→2.0, SDK 34→35, JVM target 17). Picovoice deps disabled in this build.
- **WebView mic fix via capacitor-voice-recorder plugin** (May 10, 2026) — Diagnosed `NotReadableError` on native APK = Chromium WebView refusing getUserMedia from remote origin. Solution: VoiceRecorder plugin (uses native AudioRecord). Plus browser-side WAV re-encoding so OpenAI Whisper accepts the audio. **TESTED & WORKING — Yaar mic on APK fully functional**.
- **ElevenLabs direct-from-browser TTS** (May 9, 2026) — Frontend → ElevenLabs API directly (bypasses Railway). API key stored in browser localStorage. Settings page has new ElevenLabs section.
- **Web Speech API wake word** (May 10, 2026) — New `WebSpeechWakeWord.jsx` replaces Picovoice (Picovoice signup pending commercial review). Auto-restarts on Android timeout, pauses during Yaar TTS and active recording. Free, no API key, works in browser + APK. Limitation: app must be open (no screen-off listening).
- **Resemblyzer voiceprint (Phase 1)** (May 10, 2026) — Backend `/api/voiceprint/{enroll,verify,status,delete}` using `resemblyzer` (256-d speaker embeddings, ~95% accuracy). New `EnrollVoiceprintV2` dialog: 3-take passphrase enrollment with quality scoring (avg pairwise cosine ≥ 0.65). Stores normalized mean embedding in MongoDB. **Tested locally (enroll + verify + status + delete all 200 OK).** Backend deps: `resemblyzer`, `librosa`, `soundfile`, torch ~420MB. **NOT yet wired into voice-lock guard on sensitive pages — that's the next step.**

## Active blockers
- **Yaar (companion chat) failing in production with "Couldn't reach Yaar"** — but `/api/voice/transcribe` works fine (confirms `EMERGENT_LLM_KEY` IS set, MongoDB IS connected). Issue is specific to `/api/companion/chat`. Needs investigation in next session.
- **Railway↔GitHub OAuth broken** (May 9, 2026) — Railway error "Problem completing OAuth login" when reconnecting GitHub. Backend changes can't auto-deploy until resolved. User can wait for Railway-side fix or sign in to Railway via email instead of GitHub.
- **MongoDB Atlas migration complete** (May 9, 2026) — User created fresh cluster after losing access to old one (broken GitHub OAuth on old MongoDB account). New cluster: user `qasim3638_db_user`, db `lifeblueprint`, IP allowlist `0.0.0.0/0`. URL-encoded password in connection string.

## Roadmap (priority order)

### P1 — Hands-free Yaar (user requested, next session)
- **Level 3**: Custom "Hey Yaar" wake word using Picovoice Porcupine + Android foreground service (2-3 sessions) — primary priority
- **Level 1**: Shake-to-talk gesture (quick add once Level 3 voice pipeline exists)
- ~~Level 2 Google Assistant~~ — **SKIPPED per user decision**

### P1 — Yaar Whisper Mode (lives inside Phase B service)
Discreet reminders: never blasts aloud first. Yaar gently summons → waits for consent → then speaks.
- Default ALL reminders: discreet (chime + optional soft name)
- Repeats until user responds OR max-attempts hit, then quietly drops to notification badge
- Defaults: soft chime / "Qasim" / 30s gap / 5 attempts / fallback = badge
- All four configurable in Settings:
  - Summon style: chime-only / chime+name / name-only
  - Summon name: free text (Qasim / Bhai / Jaan / custom)
  - Gap between attempts: 10s / 20s / 30s / 1m / 2m / 5m
  - Max attempts: 1-10 then fallback (silent / badge / vibration only)
- Per-reminder override flag when creating reminder
- Once user responds (any wake-trigger), Yaar speaks full reminder + follow-ups (mark done / snooze / move)
- Mode toggles (Home/Out/Quiet/Sleep): **rejected by user** — per-reminder enough
- Why Phase B: needs always-on foreground service to chime even when app closed/locked + recognize wake response

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
