# Life Blueprint — Deploy backend to Railway + MongoDB Atlas

One-time setup, ~20 minutes. Result: a permanent backend URL your Android app can hit forever, even when your laptop is off.

---

## Part A — MongoDB Atlas (free, 5 min)

1. Go to https://www.mongodb.com/cloud/atlas/register and sign up (Google sign-in is fastest).
2. Pick **"M0 — Free"** cluster. Region: pick the one closest to you (e.g., AWS Mumbai if you're in India).
3. While the cluster spins up (~2 min), create a database user:
   - **Database Access → Add New Database User**
   - Username: `lifeblueprint`
   - Password: click **Autogenerate** → **copy & save** the password somewhere safe
   - Built-in role: **Read and write to any database**
4. **Network Access → Add IP Address → Allow Access from Anywhere** (0.0.0.0/0).
   *(Required because Railway IPs change; the username/password is what protects you.)*
5. Once the cluster is green, click **Connect → Drivers → Python**:
   - Copy the connection string. It looks like:
     ```
     mongodb+srv://lifeblueprint:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
     ```
   - Replace `<password>` with the password you saved in step 3.
   - **Save this whole string** — this is your `MONGO_URL` for Railway.

---

## Part B — Railway (5 min)

1. Go to https://railway.app and log in (you already have an account).
2. **New Project → Deploy from GitHub repo** → pick `qasim3638/Life`.
3. Railway will auto-create a service. Click on it.
4. **Settings → Root Directory** → set to `backend`
   *(This tells Railway your Python app lives in the `/backend` folder, not the repo root.)*
5. **Variables** tab → add these env vars one by one (click "+ New Variable" for each):
   ```
   MONGO_URL        = <the string you copied from Atlas, with password replaced>
   DB_NAME          = lifeblueprint
   CORS_ORIGINS     = *
   EMERGENT_LLM_KEY = sk-emergent-d1d9701760e8962052
   ```
6. **Settings → Networking → Generate Domain** → Railway gives you a URL like:
   ```
   https://life-production-abcd.up.railway.app
   ```
   **Copy this URL** — you'll need it for the next step.
7. Wait ~2 min for the first deploy. Logs tab should show:
   ```
   Uvicorn running on http://0.0.0.0:XXXX
   Seed data ready.
   ```
8. Test in browser: visit `https://<your-railway-url>/api/` — should return:
   ```json
   {"message": "Life Blueprint API", "status": "ok"}
   ```

✅ Backend is live forever.

---

## Part C — Point the Android app at Railway (I'll do this for you)

Once you give me your Railway URL, I'll update:
- `/app/frontend/.env` → `REACT_APP_BACKEND_URL=<your railway URL>`
- `/app/frontend/capacitor.config.json` → `server.url` → `<your railway URL>`

You then commit + push, pull on your laptop, and run the final 3 commands:
```bash
cd Life/frontend
yarn install
npx cap sync android
npx cap open android
# press ▶ Run in Android Studio
```

---

## Caveats / good to know

- **Free tier limits**: Atlas free is 512 MB. Plenty for personal journal/chat for years.
- **File uploads** (any photos/audio you upload through the app): stored on Railway's ephemeral disk, will be **wiped on every redeploy**. If you start using uploads heavily, attach a Railway **Volume** (Settings → Volumes) to `/app/uploads` — costs ~$0.25/GB/mo.
- **Cold starts**: Railway Hobby keeps services warm 24/7. No cold starts.
- **Logs**: Railway dashboard → your service → **Deployments → View Logs**. Useful when debugging.
- **Cost monitor**: Railway dashboard → top-left avatar → **Account → Usage**. Set a budget alert at $7/mo for safety.

---

## Updating the backend later

Any time you want to push changes:
1. In Emergent, click **Save to GitHub** (or push from your laptop)
2. Railway auto-detects the new commit and redeploys in ~60 sec
3. Your Android app uses the new backend immediately — no APK rebuild needed
