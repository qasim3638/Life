/**
 * Direct browser → ElevenLabs API helper.
 *
 * Bypasses our Railway backend entirely (which is missing the elevenlabs
 * Python package and we can't redeploy right now). The key stays in
 * localStorage on the user's own device — single-user personal app.
 *
 * Public endpoint: POST https://api.elevenlabs.io/v1/text-to-speech/{voiceId}
 * Returns: audio/mpeg blob
 */

const KEY_STORAGE = "eleven_api_key";
const VOICE_STORAGE = "eleven_voice_id";

// Default to "Adam" — warm, mature male, multilingual-capable
export const DEFAULT_VOICE_ID = "pNInz6obpgDQGcFmaJgB";

export const elevenStore = {
  getKey: () => localStorage.getItem(KEY_STORAGE) || "",
  setKey: (k) => {
    if (k && k.trim()) localStorage.setItem(KEY_STORAGE, k.trim());
    else localStorage.removeItem(KEY_STORAGE);
  },
  getVoiceId: () => localStorage.getItem(VOICE_STORAGE) || DEFAULT_VOICE_ID,
  setVoiceId: (v) => {
    if (v && v.trim()) localStorage.setItem(VOICE_STORAGE, v.trim());
    else localStorage.removeItem(VOICE_STORAGE);
  },
  hasKey: () => !!localStorage.getItem(KEY_STORAGE),
};

/**
 * Call ElevenLabs TTS directly. Returns a Blob (audio/mpeg) or throws.
 */
export async function elevenSpeak(text, opts = {}) {
  const key = opts.apiKey || elevenStore.getKey();
  if (!key) throw new Error("No ElevenLabs API key set");

  const voiceId = opts.voiceId || elevenStore.getVoiceId();
  const trimmed = (text || "").trim().slice(0, 4000);
  if (!trimmed) throw new Error("Empty text");

  const url = `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "xi-api-key": key,
      Accept: "audio/mpeg",
    },
    body: JSON.stringify({
      text: trimmed,
      model_id: "eleven_multilingual_v2",
      voice_settings: {
        stability: 0.55,
        similarity_boost: 0.75,
        style: 0.3,
        use_speaker_boost: true,
      },
    }),
  });

  if (!res.ok) {
    let detail = "";
    try { detail = (await res.text()).slice(0, 120); } catch {}
    throw new Error(`ElevenLabs ${res.status}: ${detail}`);
  }
  return await res.blob();
}
