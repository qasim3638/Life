# Drop your Picovoice Porcupine files here

Required files (the app will 404 silently without these):

1. **`hi_yaar.ppn`** — your trained "Hi Yaar" wake word, Web (WASM) platform
   - Created at https://console.picovoice.ai → Porcupine → Train Wake Word
   - Type "Hi Yaar" → Train → Download → select **Web (WASM)** → unzip → rename the `.ppn` inside to `hi_yaar.ppn`

2. **`porcupine_params.pv`** — English base model
   - Download from: https://github.com/Picovoice/porcupine/raw/master/lib/common/porcupine_params.pv
   - Rename file to exactly `porcupine_params.pv`

Both files go here: `/frontend/public/models/`

Then:
- Commit to GitHub
- Vercel auto-redeploys
- In the app tap the gear icon near the mic → paste Picovoice AccessKey → toggle "Hi Yaar" on
- Say "Hi Yaar" — mic should auto-start recording
