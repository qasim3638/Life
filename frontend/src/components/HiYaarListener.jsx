// Re-export wake settings from the new Web Speech-based listener
export { getWakeEnabled, setWakeEnabled } from "./WebSpeechWakeWord";

// Legacy Picovoice key helpers — kept for backward-compat with WakeSettings UI
// (the UI's "Hi Yaar" toggle still works because of the re-export above).
const KEY_STORAGE = "life_picovoice_key";
export const getPicovoiceKey = () => localStorage.getItem(KEY_STORAGE) || "";
export const setPicovoiceKey = (k) => localStorage.setItem(KEY_STORAGE, k || "");

// Stub component — actual listening is now done by WebSpeechWakeWord
export default function HiYaarListener() { return null; }
