/**
 * Brief schedule lives in localStorage, not on backend (single-user app).
 * Shape:
 *   [{ id, kind: "morning"|"midday"|"evening"|"custom", time: "08:00", enabled: true, label?, prompt? }]
 */

const KEY = "yaar_brief_schedule_v1";
const FIRED_KEY = "yaar_brief_fired_v1"; // {brief_id__YYYY-MM-DD: true}

export const DEFAULT_BRIEFS = [
  { id: "morning", kind: "morning", time: "08:00", enabled: true, label: "Morning brief" },
  { id: "midday",  kind: "midday",  time: "13:00", enabled: false, label: "Midday check-in" },
  { id: "evening", kind: "evening", time: "21:00", enabled: true, label: "Evening wind-down" },
];

export function loadBriefs() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || "null");
    if (!Array.isArray(raw)) return [...DEFAULT_BRIEFS];
    // ensure defaults are present (preserve user's overrides)
    const ids = new Set(raw.map(b => b.id));
    for (const def of DEFAULT_BRIEFS) {
      if (!ids.has(def.id)) raw.push({ ...def });
    }
    return raw;
  } catch {
    return [...DEFAULT_BRIEFS];
  }
}

export function saveBriefs(briefs) {
  localStorage.setItem(KEY, JSON.stringify(briefs));
}

export function isFiredToday(briefId) {
  const today = new Date();
  const key = `${briefId}__${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  try {
    const map = JSON.parse(localStorage.getItem(FIRED_KEY) || "{}");
    return !!map[key];
  } catch { return false; }
}

export function markFiredToday(briefId) {
  const today = new Date();
  const key = `${briefId}__${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  let map = {};
  try { map = JSON.parse(localStorage.getItem(FIRED_KEY) || "{}"); } catch {}
  // Prune entries older than 14 days
  const cutoff = Date.now() - 14 * 24 * 60 * 60 * 1000;
  const cutoffStr = new Date(cutoff).toISOString().slice(0, 10);
  for (const k of Object.keys(map)) {
    const d = k.split("__")[1] || "";
    if (d && d < cutoffStr) delete map[k];
  }
  map[key] = true;
  localStorage.setItem(FIRED_KEY, JSON.stringify(map));
}

export function newCustomBrief() {
  return {
    id: `custom-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    kind: "custom",
    time: "09:00",
    enabled: true,
    label: "Custom brief",
    prompt: "Give me a one-paragraph nudge for what to focus on next.",
  };
}
