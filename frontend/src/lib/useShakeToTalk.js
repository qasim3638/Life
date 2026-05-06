/**
 * useShakeToTalk — Level 1 hands-free trigger.
 *
 * Fires a `life:wake` event when the user shakes the phone firmly.
 * Uses browser DeviceMotion API — works inside Capacitor WebView while app
 * is in the foreground. (For screen-off shake detection we'd need a native
 * foreground service, same as the wake-word Phase B.)
 *
 * Config: localStorage `life_shake_enabled` = "on" | "off"
 */
import { useEffect } from "react";

const SHAKE_PREF_KEY = "life_shake_enabled";
const SHAKE_THRESHOLD_G = 22;     // acceleration delta (m/s²) — ~2.2 g
const SHAKE_COOLDOWN_MS = 2500;   // prevent double-fires
const IOS_PERMISSION_KEY = "life_shake_ios_granted";

export const getShakeEnabled = () =>
  (localStorage.getItem(SHAKE_PREF_KEY) || "off") === "on";
export const setShakeEnabled = (on) =>
  localStorage.setItem(SHAKE_PREF_KEY, on ? "on" : "off");

// iOS 13+ requires an explicit permission request after a user gesture.
export async function requestShakePermissionIfNeeded() {
  const needsPerm = typeof DeviceMotionEvent !== "undefined"
    && typeof DeviceMotionEvent.requestPermission === "function";
  if (!needsPerm) return "granted";
  try {
    const res = await DeviceMotionEvent.requestPermission();
    if (res === "granted") localStorage.setItem(IOS_PERMISSION_KEY, "1");
    return res;
  } catch {
    return "denied";
  }
}

export default function useShakeToTalk() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    let lastShake = 0;
    let last = { x: 0, y: 0, z: 0, t: 0 };
    let bound = false;

    const onMotion = (e) => {
      if (!getShakeEnabled()) return;
      const a = e.accelerationIncludingGravity || e.acceleration;
      if (!a) return;
      const now = Date.now();
      if (!last.t) { last = { x: a.x || 0, y: a.y || 0, z: a.z || 0, t: now }; return; }
      const dt = now - last.t || 1;
      const delta = (
        Math.abs((a.x || 0) - last.x)
        + Math.abs((a.y || 0) - last.y)
        + Math.abs((a.z || 0) - last.z)
      ) * 1000 / dt;
      last = { x: a.x || 0, y: a.y || 0, z: a.z || 0, t: now };
      if (delta > SHAKE_THRESHOLD_G && now - lastShake > SHAKE_COOLDOWN_MS) {
        lastShake = now;
        window.dispatchEvent(new CustomEvent("life:wake", { detail: { label: "shake" } }));
      }
    };

    const bind = () => {
      if (bound) return;
      window.addEventListener("devicemotion", onMotion, { passive: true });
      bound = true;
    };
    const unbind = () => {
      if (!bound) return;
      window.removeEventListener("devicemotion", onMotion);
      bound = false;
    };

    bind();

    // React to settings flips
    const onPref = () => {
      if (getShakeEnabled()) bind(); else unbind();
    };
    window.addEventListener("life:wake-settings", onPref);
    return () => {
      window.removeEventListener("life:wake-settings", onPref);
      unbind();
    };
  }, []);
}
