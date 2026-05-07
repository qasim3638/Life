# Phase B + Yaar Whisper Mode — Complete Setup

Everything for "Hi Yaar" with screen off + discreet reminders that summon you gently.

---

## What's shipped this session

### ✅ Phase A web (already shipped previous session)
- Foreground "Hi Yaar" wake word
- Shake-to-talk
- Eagle voiceprint verification

### ✅ Yaar Whisper Mode (NEW — fully testable on Vercel preview today)
- New page **/reminders** in sidebar
- Backend `/api/reminders` + `/api/reminders/whisper/settings`
- WhisperEngine polls every 30s, plays soft chime (mp3 or generated tone)
  + optional TTS of your name on each attempt
- User responds → Yaar speaks the reminder properly
- Per-reminder overrides for summon style/name/gap/max
- All 5 settings configurable (style, name, gap, max attempts, fallback)

### ✅ Phase B native (NEW — needs Android Studio rebuild + your testing)
- `HandsFreeService.kt` — foreground service running Porcupine + Eagle
- `HandsFreePlugin.kt` — Capacitor plugin bridge to JS
- AndroidManifest updated (mic + foreground service + notifications perms)
- Picovoice Android SDKs added to Gradle
- `handsFreeBridge.js` — JS wrapper auto-copies models from web to filesDir
- Toggle in Settings: "Always-on listening" (only enabled in installed app)

---

## Setup checklist — do these in order

### 1. Push code to GitHub (1 min)
Click **"Save to GitHub"** in Emergent. Vercel auto-redeploys frontend in ~90s. Railway auto-redeploys backend in ~60s.

### 2. Get model files (5 min if not done yet)
You need 3 files in `frontend/public/models/`:

- **`hi_yaar.ppn`** (Web/WASM platform) — train at https://console.picovoice.ai → Porcupine → Train → "Hi Yaar" → Web (WASM) → unzip → rename
- **`hi_yaar_android.ppn`** (Android platform) — same wake word, but trained for Android target. Re-download from console picking Android. **Rename to `hi_yaar.ppn` for the Android build location** (we use the same filename, different folder)
   *(Actually — see step 4: the JS bridge fetches the same `/models/hi_yaar.ppn` file. We use the Web build for both. If Picovoice rejects the Web binary on Android, you'll need a separate Android-trained .ppn — easy fix in next session.)*
- **`porcupine_params.pv`** — https://github.com/Picovoice/porcupine/raw/master/lib/common/porcupine_params.pv
- **`eagle_params.pv`** — https://github.com/Picovoice/eagle/raw/main/lib/common/eagle_params.pv

Put all in `frontend/public/models/` then commit + push:

```bash
cd ~/Life
git pull
# copy 4 files into frontend/public/models/
git add frontend/public/models/
git commit -m "voice models for phase A + B"
git push
```

### 3. Test Whisper Mode on web RIGHT NOW (no rebuild needed)
1. Open Vercel app on phone (or laptop): `https://life-5m18.vercel.app/reminders`
2. Set "Summon name" to "Bhai" or "Jaan"
3. Create a reminder for 1 minute from now: title "Drink water", body "10 sips please"
4. Wait. Within 30s of fire-time you'll see the summon banner + hear the chime
5. Tap "I'm here" → Yaar reads your reminder out loud properly

### 4. Build Phase B native (Android Studio)

```bash
cd ~/Life/frontend
yarn install
yarn build
npx cap sync android
npx cap open android
```

In Android Studio:
1. **Wait for Gradle sync** (~5 min — downloads Picovoice Android SDKs ~30MB)
2. ⚠️ **You may see Gradle errors on first sync** — most likely:
   - "Could not resolve ai.picovoice:porcupine-android" → Maven Central is down, just retry
   - "Kotlin version mismatch" → Tools → Update Kotlin → Apply
   - "minSdk too low for FOREGROUND_SERVICE_MICROPHONE" → check `variables.gradle`, set minSdk to 24+
3. Once Gradle is green, ▶ **Run** → installs on your S24 Ultra
4. App opens → tap gear icon → toggle **"Always-on listening"** ON
5. Android prompts:
   - "Allow Life Blueprint to record audio?" → **Allow**
   - "Allow notifications?" → **Allow**
6. **Persistent notification appears**: "Yaar is listening" — this is required by Android, can't be hidden
7. **Lock your phone, screen off** → say "Hi Yaar" → app should wake mic + open recording
8. Speak → Yaar replies through phone speaker
9. Voiceprint check (if enrolled) happens automatically — only your voice triggers

### 5. Send me logs if anything breaks
With phone connected to laptop:
```bash
adb logcat | grep -E "HandsFreeService|HandsFreePlugin|Capacitor"
```
Send the output. Native plugin code rarely runs perfectly first-try; expect 1-2 small fixes.

---

## How Whisper Mode works (in detail)

```
Reminder fire_at hits → Backend marks status=summoning when polled
                    ↓
Frontend WhisperEngine polls /api/reminders/poll every 30s
                    ↓
Got a reminder → starts summon loop
                    ↓
   ┌──── Chime + (optional) "Bhai?" in soft TTS ────┐
   │           Wait `gap_seconds`                    │
   │           Repeat                                │
   └─────────── until one of: ──────────────────────┘
                    │
   ┌────────────────┼────────────────┬───────────────┐
   ▼                ▼                ▼               ▼
"I'm here" (tap)  Wake word fires  Snooze 10m    Max attempts hit
   ↓                ↓                ↓               ↓
acknowledged    acknowledged    snoozed      failed → fallback action
   ↓                ↓                ↓
Yaar speaks    Yaar speaks    no further chimes
the reminder   the reminder   for 10 min
```

## How Phase B native works

```
HandsFreeService (foreground, always alive) ───┐
   │                                            │
   │ VoiceProcessor → Porcupine.process(frame)  │
   │            ↓                               │
   │     "Hi Yaar" detected                     │
   │            ↓                               │
   │     If voiceprint enrolled:                │
   │        Buffer ~1.6s frames                 │
   │        Eagle.process → avg score           │
   │        score >= 0.6? → broadcast WAKE     │
   │     Else: broadcast WAKE immediately       │
   │                                            │
   └────── Broadcast → HandsFreePlugin ─────────┘
                            ↓
              notifyListeners('wake', {})
                            ↓
              JS WakeSettings useEffect:
                window.dispatchEvent('life:wake')
                            ↓
              VoiceMicButton starts recording
                            ↓
              User speaks → Whisper STT → Companion API
                            ↓
              Yaar replies → OpenAI TTS → audio plays
                  (works through MediaSession on lock screen)
                            ↓
              Recording done → 'life:resume-wake' fires
                            ↓
              (Phase B: nothing — service is already listening)
```

---

## Known limitations & realities

- Phase B foreground service shows a **persistent notification** — Android forces this. Cannot be hidden.
- Battery: ~2-4% per day extra for always-on mic processing
- Lock-screen TTS requires MediaSession integration — currently audio plays via standard Audio() element which Android usually allows in foreground service apps. If not, we'd add a tiny native TTS fallback (1-line addition).
- iOS: no Phase B yet (different APIs, requires separate Swift implementation)
- The 4 model files in `frontend/public/models/` ship with the Vercel deploy AND get copied into Android filesDir on first start. ~3MB total APK bloat.

---

## Files reference

### Backend
- `backend/routes/reminders.py` — Whisper endpoints + Reminder model
- `backend/routes/speaker.py` — Eagle voiceprint storage
- `backend/server.py` — wires both routers

### Frontend (web layer)
- `src/components/WhisperEngine.jsx` — polls + summons (mounted globally)
- `src/components/WakeSettings.jsx` — gear icon dialog (now with Always-on toggle)
- `src/components/EnrollVoiceprint.jsx` — voiceprint enrollment modal
- `src/components/HiYaarListener.jsx` — Phase A web Porcupine + Eagle
- `src/components/VoiceMicButton.jsx` — mic recording UI (catches life:wake)
- `src/lib/handsFreeBridge.js` — JS↔native plugin wrapper
- `src/lib/useShakeToTalk.js` — shake gesture
- `src/pages/Reminders.jsx` — full reminder management page

### Frontend (native, Phase B)
- `android/app/src/main/AndroidManifest.xml` — service + permissions
- `android/app/src/main/java/com/qasim/lifeblueprint/HandsFreeService.kt`
- `android/app/src/main/java/com/qasim/lifeblueprint/HandsFreePlugin.kt`
- `android/app/src/main/java/com/qasim/lifeblueprint/MainActivity.java` — registers plugin
- `android/app/build.gradle` — Picovoice + Kotlin deps
- `android/build.gradle` — Kotlin classpath
