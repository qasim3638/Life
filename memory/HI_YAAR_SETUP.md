# "Hi Yaar" Wake Word + Shake-to-Talk — Setup (3 min)

You've shipped the code. Now 2 quick things to activate it.

---

## 1. Get a Picovoice AccessKey (free, 2 min)

1. Go to **https://console.picovoice.ai**
2. Sign up with Google or email (free tier — 3 active users, no card required)
3. Top-right → **Account** → copy your **AccessKey** (looks like `abc123…XYZ==`)
4. Keep this tab open — you'll need it in step 3

## 2. Train "Hi Yaar" wake word + download model files

1. In Picovoice Console → left sidebar → **Porcupine**
2. Click **Train Wake Word**
3. Language: **English**
4. Type the phrase: **`Hi Yaar`**
5. (Optional) Click the mic button, say "Hi Yaar" a few times to test pronunciation
6. Click **Train** → wait ~15 seconds
7. Click **Download** → platform: **Web (WASM)** → downloads a `.zip`
8. Unzip it. Inside you'll see:
   - `Hi-Yaar_en_wasm_v3_0_0.ppn` (or similar) → **rename to `hi_yaar.ppn`**

Also grab the base English model:
- https://github.com/Picovoice/porcupine/raw/master/lib/common/porcupine_params.pv
- Save as `porcupine_params.pv`

Place **both** files in: `/frontend/public/models/`

```
frontend/
  public/
    models/
      hi_yaar.ppn           ← your trained wake word
      porcupine_params.pv   ← english base model
      README.md             (already exists, ignore)
```

## 3. Push + activate

1. Click **"Save to GitHub"** in Emergent (pushes code + model files)
2. Vercel auto-redeploys in ~90 sec
3. On your phone, open Life Blueprint
4. Tap the **gear icon** (near the voice mic, bottom-right)
5. Paste your Picovoice AccessKey → **Save**
6. Toggle **"Hi Yaar"** on
7. Say **"Hi Yaar"** → mic should buzz, start recording, you talk, Yaar replies

## 4. Shake to talk

Same settings panel → toggle **"Shake to talk"** on. Then firmly shake your phone (like you're tossing a dice) → mic opens instantly. Great for when you don't want to say the wake word out loud (e.g., you're in a meeting).

---

## ⚠️ Limitations of this phase (A)

- Works **only while the app is open** (foreground)
- Screen-off / app-closed wake word = Phase B (native Android foreground service) — planned
- If you switch to another app, Porcupine stops listening

## Battery tip

If you leave "Hi Yaar" on 24/7 with the app in foreground, expect ~8-12% extra battery per hour (continuous mic + WASM processing). Best used when you're actively using the app.

---

## Troubleshooting

**"Paste AccessKey first"** → You tried to toggle wake word without saving the key. Paste + Save, then toggle.

**Wake word on but nothing happens when I say "Hi Yaar"** → Open your phone's browser Network tab (via `chrome://inspect`) — check if `hi_yaar.ppn` 404s. If yes, re-verify file names + location. Also check console for "AccessKey invalid" errors.

**Shake triggers randomly** → We detect ~2.2g spikes. If you walk vigorously, bump into something, etc., adjust the threshold in `useShakeToTalk.js` (constant `SHAKE_THRESHOLD_G`). Default 22 ≈ 2.2 g — raise to 30+ if too sensitive.

**Mic opens but doesn't record** → Porcupine and VoiceMicButton both need exclusive mic access. We handle handoff automatically (unsubscribe before recording). If issue persists, disable wake word, try manual tap, then re-enable.
