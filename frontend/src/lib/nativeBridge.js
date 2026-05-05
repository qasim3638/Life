/**
 * Native-only bridge (Capacitor local notifications).
 * In the web browser, all functions no-op silently.
 */
import { Capacitor } from "@capacitor/core";
import { LocalNotifications } from "@capacitor/local-notifications";

export const isNative = () => Capacitor.isNativePlatform();

/** Stable numeric id per brief — Android local notifications are keyed by int. */
const idFor = (briefId) => {
  // simple hash → positive 31-bit int
  let h = 0;
  for (let i = 0; i < briefId.length; i++) {
    h = ((h << 5) - h + briefId.charCodeAt(i)) | 0;
  }
  return Math.abs(h) || 1;
};

/** Ask permission (Android 13+ and iOS). Safe to call repeatedly. */
export async function requestNativePermission() {
  if (!isNative()) return "web";
  try {
    const { display } = await LocalNotifications.checkPermissions();
    if (display === "granted") return "granted";
    const res = await LocalNotifications.requestPermissions();
    return res.display;
  } catch {
    return "unsupported";
  }
}

/**
 * Re-register every enabled brief so the phone's OS fires a notification
 * at the configured time — even if the app is fully closed.
 *
 * Because local notifications can't run JS when they fire, the notification
 * body is a short static teaser; tapping it opens the app which then
 * fetches the fresh brief text from the backend and speaks it.
 */
export async function syncBriefsToNative(briefs) {
  if (!isNative()) return;
  try {
    // 1) Cancel everything we previously scheduled so toggles/removals stick
    const { notifications } = await LocalNotifications.getPending();
    if (notifications?.length) {
      await LocalNotifications.cancel({
        notifications: notifications.map((n) => ({ id: n.id })),
      });
    }

    const teasers = {
      morning: "Your morning brief is ready. Tap to hear it.",
      midday: "Midday check-in — tap to hear Yaar.",
      evening: "Wind-down time. Tap for your evening recap.",
      custom: "Yaar has something for you. Tap to listen.",
    };

    // 2) Build daily-repeating notifications for each enabled brief
    const toSchedule = [];
    for (const b of briefs || []) {
      if (!b.enabled) continue;
      if (!/^\d{2}:\d{2}$/.test(b.time || "")) continue;
      const [hh, mm] = b.time.split(":").map(Number);
      toSchedule.push({
        id: idFor(b.id),
        title: `Yaar · ${b.label}`,
        body: teasers[b.kind] || teasers.custom,
        schedule: {
          on: { hour: hh, minute: mm },
          repeats: true,
          allowWhileIdle: true,
        },
        extra: { briefId: b.id, kind: b.kind },
        smallIcon: "ic_stat_icon_config_sample",
        iconColor: "#59745D",
      });
    }
    if (toSchedule.length) {
      await LocalNotifications.schedule({ notifications: toSchedule });
    }
  } catch (e) {
    // Silent — web / unsupported / permission issues
    console.warn("syncBriefsToNative failed:", e?.message);
  }
}

/**
 * Subscribe to notification taps so we can open the right brief immediately.
 * Callback signature: ({ briefId, kind }) => void
 */
export function onBriefTap(callback) {
  if (!isNative()) return () => {};
  const handle = LocalNotifications.addListener("localNotificationActionPerformed", (event) => {
    const extra = event?.notification?.extra || {};
    if (extra.briefId) callback(extra);
  });
  return () => {
    try { handle.then((h) => h.remove()); } catch {}
  };
}
