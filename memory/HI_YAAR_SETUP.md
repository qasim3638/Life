# Voice features — Setup & Status

## Phase A — Foreground hands-free (SHIPPED)

### Capabilities
- ✅ "Hi Yaar" wake word (Porcupine web SDK)
- ✅ Shake-to-talk (DeviceMotion API)
- ✅ **Voiceprint verification** (Eagle web SDK) — only your voice triggers Yaar
- 🟡 Works while app is open in foreground only

### One-time setup (10 min)

1. **Picovoice AccessKey** (free)
   - Sign up: https://console.picovoice.ai
   - Account → copy AccessKey
   - In app: gear icon (near mic) → paste → Save

2. **Train "Hi Yaar" wake word** (free, 3 min)
   - Picovoice Console → Porcupine → **Train Wake Word**
   - Language: English → phrase: `Hi Yaar` → Train → Download
   - Pick **Web (WASM)** → unzip → rename to `hi_yaar.ppn`

3. **Download required model files**
   - **Porcupine base model**: https://github.com/Picovoice/porcupine/raw/master/lib/common/porcupine_params.pv
   - **Eagle base model**: https://github.com/Picovoice/eagle/raw/main/lib/common/eagle_params.pv

4. **Place all 3 files** in `/frontend/public/models/`:
   ```
   frontend/public/models/
     hi_yaar.ppn            ← your trained wake word (Web/WASM)
     porcupine_params.pv    ← english base model
     eagle_params.pv        ← speaker recognition base model
   ```

5. **Push files to GitHub** (binary files need local push — can't go through Emergent Save-to-GitHub):
   ```bash
   cd ~/Life
   git pull
   # copy the 3 files into frontend/public/models/
   git add frontend/public/models/
   git commit -m "voice models"
   git push
   ```
   Vercel auto-redeploys in ~90s.

6. **Activate in the app**:
   - Open Life Blueprint
   - Tap gear icon near mic
   - Toggle **"Hi Yaar"** on
   - Tap **"Enroll"** under Voiceprint → speak naturally for ~30s until 100% → **Save voiceprint**
   - Optionally: toggle **"Shake to talk"** on too

7. **Test**:
   - Say "Hi Yaar" → mic should buzz "Yaar is listening…" → speak → Yaar responds
   - Have someone else say "Hi Yaar" → nothing happens (voiceprint blocks)
   - Shake phone firmly → mic opens (no voiceprint check on shake — you have the phone)

### Backend endpoints
- `PUT /api/speaker/profile` — `{profile_base64, threshold}` → save Eagle profile bytes
- `GET /api/speaker/profile` — returns the profile + threshold (used at app boot)
- `GET /api/speaker/status` — returns `{enrolled, threshold}` (cheap, used in Settings UI)
- `DELETE /api/speaker/profile` — clear voiceprint

Profile is stored in `db.speaker_profile` collection, single document `_id: "primary"`.

### Threshold tuning
- Default: 0.6 — balanced for casual home use
- Score >= threshold = your voice; score < = imposter
- If your voice gets rejected often, lower to 0.55 (in DB or via re-enrollment)
- If random voices trigger it, raise to 0.7

---

## Phase B — Background / locked phone (NEXT SESSION)

### Goal
Wake word + voiceprint working with screen off, app closed, phone locked.

### Why it requires native code
- Web SDK (Phase A) only runs while WebView is active
- Capacitor pauses WebView when app is backgrounded
- Need a native Android Service (foreground type) to keep Porcupine + Eagle running on a separate thread
- That service needs to bridge wake-events back to the WebView when user unlocks / opens app

### Architecture sketch (Phase B)
```
┌──────────────────────────────────────────────────────┐
│  Android Foreground Service (always running)         │
│  ┌────────────────────────────────────────────────┐  │
│  │ PvRecorder (continuous mic)                    │  │
│  │      │                                         │  │
│  │      ▼                                         │  │
│  │ Porcupine.process(frame) ─── if "Hi Yaar":    │  │
│  │      │                                         │  │
│  │      ▼                                         │  │
│  │ Eagle.process(frames over 1.5s) ─── if match:│  │
│  │      │                                         │  │
│  │      ▼                                         │  │
│  │ Broadcast life.WAKE_INTENT                     │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────┐
│  Capacitor MainActivity (resumes if WebView active)  │
│  Plays a chime via MediaSession (works lock-screen)  │
│  Records via existing MediaRecorder if app open      │
│  OR triggers TTS conversation via SystemTextToSpeech │
└──────────────────────────────────────────────────────┘
```

### Files to add (Phase B)
- `android/app/src/main/java/com/lifeblueprint/HandsFreeService.kt` — foreground service
- `android/app/src/main/java/com/lifeblueprint/HandsFreePlugin.kt` — Capacitor plugin
- `android/app/src/main/AndroidManifest.xml` — add `<service>`, `FOREGROUND_SERVICE_MICROPHONE` permission
- `frontend/src/lib/handsFreeBridge.js` — JS wrapper for Plugin
- Use Picovoice Eagle Android SDK (`ai.picovoice:eagle-android` Gradle dep)
- Use Picovoice Porcupine Android SDK (already partially set up via Capacitor)

### User-visible changes (Phase B)
- Persistent notification: "Yaar is listening — tap to silence"
   - Cannot be hidden (Android 14 requirement)
- Battery: ~2-4% per day extra
- New permission prompt: "Allow recording audio at all times"
- Settings toggle: "Always-on hands-free" (off by default — opt-in)

### Realistic effort
- 2-3 sessions of work: scaffold plugin → wire to React → test on user's S24 Ultra → fix Android 14 permission edge cases

---

## Troubleshooting (Phase A)

**"Save your AccessKey first"** — Settings → paste AccessKey → Save before toggling wake word.

**Wake word toggle on but nothing happens when I say "Hi Yaar"** —
1. Open `chrome://inspect` on laptop with phone connected
2. Inspect the WebView → Console tab
3. Look for "HiYaar wake word init failed" → most likely cause: 404 on one of the model files. Verify files are in `frontend/public/models/` and pushed.

**Voiceprint enrollment stuck below 100%** — speak more, in different sentences. Eagle wants ~30s of varied speech. Check feedback below the dial — "Speak naturally" / "Quieter spot" guides you.

**Voiceprint always rejects me** — too high threshold. Re-enroll in a quiet room with consistent voice tone. Or manually lower threshold by deleting the profile and re-saving with `threshold: 0.5`.

**Shake triggers from walking** — adjust `SHAKE_THRESHOLD_G` in `useShakeToTalk.js` (default 22 ≈ 2.2g, raise to 30+ for less sensitive).
