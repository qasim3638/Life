# Life Blueprint — Android setup (one-time, ~45 min)

You're now ready to install Life Blueprint on your Android phone as a real app, with **lock-screen notifications** for Yaar's voice briefs that fire even when the app is fully closed.

## What you need

- **Your Android phone**
- **A USB cable**
- **A computer** (Windows / Mac / Linux all fine)
- **A free Google account** (you already have one)

That's it. No fees. No App Store. No Apple Developer account.

---

## Step 1 — Download & install Android Studio

1. Go to https://developer.android.com/studio
2. Click **Download Android Studio** → install with default options.
3. First launch will take ~5 min to download SDK files. Let it.

## Step 2 — Get your Life Blueprint code onto your computer

The whole Capacitor project I just set up lives at `/app/frontend/android` in your Emergent workspace.

**Easiest way:** click **"Save to GitHub"** in the Emergent chat input → push to a private repo → on your computer run:
```bash
git clone <your-repo-url>
cd <repo>/frontend
```

(If you don't want GitHub: in Emergent, use **Download Code** to get a zip of the project and unzip it on your computer.)

## Step 3 — Install dependencies (one-time)

In the `frontend` folder on your computer:
```bash
yarn install
```

Takes ~3 min the first time.

## Step 4 — Open the Android project in Android Studio

```bash
npx cap open android
```

This opens Android Studio with the Life Blueprint project. **Wait for "Gradle sync"** to finish (5-10 min the first time, you'll see a progress bar at the bottom).

## Step 5 — Enable Developer Mode + USB Debugging on your phone

On your Android phone:
1. **Settings → About phone → Software information**
2. Tap **Build number** seven times until you see "You are now a developer"
3. Go back → **Settings → Developer options** → turn on **USB debugging**
4. Plug your phone into your computer with the USB cable
5. Your phone will pop up "Allow USB debugging from this computer?" — tap **Allow**

## Step 6 — Run

In Android Studio:
1. Top of the screen: a dropdown shows your phone name
2. Press the green ▶ **Run** button
3. Wait ~30 seconds the first time → app installs and opens on your phone

You're done. Life Blueprint is now a real app on your home screen.

## Step 7 — Set up your briefs

Inside the app:
1. **Companion → 🔔 Briefs button** in the header
2. Tap **Enable** for phone notifications (Android will ask permission once)
3. Set your morning / midday / evening times — or add custom briefs
4. **Lock your phone**

At your set time, your phone's lock screen will buzz: "Yaar · Morning brief — Your morning brief is ready. Tap to hear it." Tap → app opens → Yaar speaks today's fresh summary in his coral voice.

---

## Updating the app later

Whenever I change anything in Emergent (or you redeploy):
- The app pulls the latest UI **from the live website automatically** — no rebuild needed
- Only the **native Capacitor settings** (notification permission, plugin updates) need a fresh APK install

So 99% of changes you'll never need to rebuild for.

If you do need to push a native change:
```bash
cd <repo>/frontend
npx cap sync android
npx cap open android
# press ▶ Run
```

---

## When you switch to iOS later

Just run on your future Mac:
```bash
npx cap add ios
npx cap open ios
# press Run in Xcode
```

Same code. Same notifications. 30 seconds.

---

## Common issues

**"Phone not detected in Android Studio"**
- Make sure USB debugging is on
- Try a different cable (some are charge-only)
- On Windows: install Google's USB driver

**"Gradle sync failed"**
- File → Invalidate Caches → restart Android Studio
- Make sure you have the latest Android Studio

**"App opens but won't play voice"**
- Make sure you're online — voice generation calls your backend
- Phone settings → Apps → Life Blueprint → Permissions → enable Microphone

**"Notifications not firing"**
- Phone settings → Apps → Life Blueprint → Notifications → "Allow"
- Battery optimisation: set Life Blueprint to **Not optimised** so Android doesn't suspend scheduled notifications

---

## What's special about this setup (free, lifetime)

- **No Firebase**, no server-side push, no fees
- **No Apple Developer account** ($99/year saved)
- **No App Store** review or submission
- Notifications fire **on your phone's clock**, not via a server — they work offline too
- When you tap, the app fetches **live brief content** from your Emergent backend — so the spoken text always reflects today's plan, not yesterday's
- **Your branding is baked in** — moss-green "Lb" monogram icon on your home screen, warm-beige splash screen with the Life Blueprint mark fades in for ~1.5s on launch

Welcome to your real Android app.
