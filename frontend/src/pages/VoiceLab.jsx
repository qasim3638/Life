/**
 * VoiceLab — pick Yaar's voice from OpenAI + ElevenLabs samples.
 *
 * Lets the user A/B test all available voices in 3 languages, then save
 * their pick. Backend `/api/voice/preference` stores it. The /voice/speak
 * endpoint reads it via provider="auto" mode.
 */
import React, { useEffect, useState } from "react";
import { api, API, authStore } from "../lib/api";
import { Play, Square, Check, Loader2, Volume2 } from "lucide-react";
import { toast } from "sonner";

const ELEVEN_VOICES = [
  { id: "pNInz6obpgDQGcFmaJgB", label: "Adam",      vibe: "Warm, mature male" },
  { id: "ErXwobaYiN019PkySvjV", label: "Antoni",    vibe: "Gentle younger male" },
  { id: "TxGEqnHWrfWFTfGW9XjX", label: "Josh",      vibe: "Deep, calm male" },
  { id: "VR6AewLTigWG4xSOukaG", label: "Arnold",    vibe: "Strong, confident male" },
  { id: "yoZ06aMxZJJ28mfd3POQ", label: "Sam",       vibe: "Soft, friendly male" },
  { id: "EXAVITQu4vr4xnSDxMaL", label: "Bella",     vibe: "Soft, soothing female" },
  { id: "XB0fDUnXU5powFXDhCwa", label: "Charlotte", vibe: "Warm, emotional female" },
  { id: "AZnzlk1XvdvUeBnXmlld", label: "Domi",      vibe: "Strong, confident female" },
  { id: "MF3mGyEYCl7XYWbV9V6O", label: "Elli",      vibe: "Young, gentle female" },
  { id: "piTKgcLEGmPE4e6mEKli", label: "Nicole",    vibe: "Whispery, intimate female" },
];

const OPENAI_VOICES = [
  { id: "coral",   label: "Coral",   vibe: "Warm, friendly (default)" },
  { id: "nova",    label: "Nova",    vibe: "Energetic female" },
  { id: "shimmer", label: "Shimmer", vibe: "Soft, light female" },
  { id: "alloy",   label: "Alloy",   vibe: "Neutral, clear" },
  { id: "echo",    label: "Echo",    vibe: "Calm male" },
  { id: "fable",   label: "Fable",   vibe: "British storyteller" },
  { id: "onyx",    label: "Onyx",    vibe: "Deep male" },
  { id: "sage",    label: "Sage",    vibe: "Older wise voice" },
  { id: "ash",     label: "Ash",     vibe: "Direct, clear male" },
];

const LANGS = [
  { code: "en", label: "English" },
  { code: "hi", label: "Hindi" },
  { code: "ur", label: "Urdu" },
];

const labelKey = (id) => {
  const v = ELEVEN_VOICES.find((x) => x.id === id);
  return v ? v.label.toLowerCase() : "";
};

export default function VoiceLab() {
  const [pref, setPref] = useState(null);
  const [tab, setTab] = useState("elevenlabs"); // elevenlabs | openai
  const [lang, setLang] = useState("en");
  const [playingKey, setPlayingKey] = useState(null);
  const [savingId, setSavingId] = useState(null);
  const audioRef = React.useRef(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/voice/preference");
        setPref(data);
        if (data?.provider === "elevenlabs") setTab("elevenlabs");
        else setTab("openai");
      } catch {
        setPref({ provider: "openai", voice: "coral" });
      }
    })();
  }, []);

  const stop = () => {
    if (audioRef.current) {
      try { audioRef.current.pause(); } catch {}
      audioRef.current = null;
    }
    setPlayingKey(null);
  };

  const playPreset = (voice, vlang) => {
    stop();
    const key = `${voice.label.toLowerCase()}-${vlang}`;
    const url = `${API}/uploads/voice_${voice.label.toLowerCase()}_${vlang}.mp3`;
    const a = new Audio(url);
    audioRef.current = a;
    setPlayingKey(key);
    a.onended = () => setPlayingKey((k) => (k === key ? null : k));
    a.onerror = () => { toast.error("No sample for this combo yet"); setPlayingKey(null); };
    a.play().catch(() => { toast.error("Couldn't play"); setPlayingKey(null); });
  };

  const playLive = async (voiceId, provider) => {
    stop();
    const key = `live-${voiceId}-${lang}`;
    setPlayingKey(key);
    const text = lang === "hi"
      ? "Namaste Qasim. Main Yaar hoon. Aap kaise hain aaj?"
      : lang === "ur"
        ? "Salaam Qasim. Aap ka Yaar hoon. Kaisi guzar rahi hai?"
        : "Hello Qasim. Yaar here. How are you holding up today?";
    try {
      const token = authStore.getToken();
      const res = await fetch(`${API}/voice/speak`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ text, voice: voiceId, provider }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const a = new Audio(URL.createObjectURL(blob));
      audioRef.current = a;
      a.onended = () => setPlayingKey((k) => (k === key ? null : k));
      await a.play();
    } catch (e) {
      toast.error(e?.message || "Couldn't play");
      setPlayingKey(null);
    }
  };

  const save = async (provider, voice) => {
    setSavingId(`${provider}-${voice}`);
    try {
      const { data } = await api.put("/voice/preference", { provider, voice });
      setPref(data);
      toast.success(`Yaar will speak with ${labelKey(voice) || voice} from now on`);
    } catch {
      toast.error("Couldn't save");
    } finally {
      setSavingId(null);
    }
  };

  if (!pref) return <div className="p-8 text-[#6B7270]">Loading…</div>;

  const isPicked = (provider, voice) =>
    pref.provider === provider && pref.voice === voice;

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 space-y-8" data-testid="voicelab-page">
      <header>
        <p className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C]">Yaar</p>
        <h1 className="font-serif text-4xl text-[#2D312E] mt-1">Voice</h1>
        <p className="text-sm text-[#6B7270] mt-2 leading-relaxed">
          Try voices in different languages. Tap ▶ to listen. Tap Save to make it Yaar's.
        </p>
        {pref && (
          <p className="text-xs text-[#59745D] mt-3">
            Currently: <strong>{pref.provider === "elevenlabs" ? labelKey(pref.voice) || "ElevenLabs" : pref.voice} ({pref.provider})</strong>
          </p>
        )}
      </header>

      {/* Provider tabs */}
      <div className="flex gap-2 border-b border-sand">
        {[
          { id: "elevenlabs", label: "ElevenLabs ($5/mo)" },
          { id: "openai", label: "OpenAI (free)" },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => { stop(); setTab(t.id); }}
            className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 ${tab === t.id ? "border-[#59745D] text-[#2D312E]" : "border-transparent text-[#9A9F9D]"}`}
            data-testid={`voicelab-tab-${t.id}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Language selector — only for preset samples */}
      {tab === "elevenlabs" && (
        <div className="flex gap-2 flex-wrap">
          <span className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C] self-center mr-2">Sample lang</span>
          {LANGS.map((l) => (
            <button
              key={l.code}
              onClick={() => setLang(l.code)}
              className={`px-3 py-1.5 rounded-full text-xs ${lang === l.code ? "bg-[#59745D] text-white" : "bg-white border border-sand text-[#6B7270]"}`}
              data-testid={`voicelab-lang-${l.code}`}
            >
              {l.label}
            </button>
          ))}
        </div>
      )}

      {/* Voice list */}
      <ul className="space-y-2" data-testid={`voicelab-list-${tab}`}>
        {(tab === "elevenlabs" ? ELEVEN_VOICES : OPENAI_VOICES).map((v) => {
          const presetKey = `${v.label.toLowerCase()}-${lang}`;
          const liveKey = `live-${v.id}-${lang}`;
          const playing = playingKey === presetKey || playingKey === liveKey;
          const picked = isPicked(tab, v.id);
          return (
            <li
              key={v.id}
              className={`rounded-2xl p-4 flex items-center justify-between gap-3 border transition-colors ${picked ? "bg-[#59745D]/5 border-[#59745D]/30" : "bg-white border-sand"}`}
              data-testid={`voicelab-item-${v.label.toLowerCase()}`}
            >
              <div className="flex-1 min-w-0">
                <p className="font-medium text-[#2D312E] flex items-center gap-2">
                  {v.label}
                  {picked && <Check size={14} className="text-[#59745D]"/>}
                </p>
                <p className="text-xs text-[#6B7270]">{v.vibe}</p>
              </div>
              <div className="flex gap-1">
                {tab === "elevenlabs" ? (
                  <button
                    onClick={() => playing ? stop() : playPreset(v, lang)}
                    className="w-9 h-9 rounded-full bg-white border border-sand flex items-center justify-center text-[#59745D] hover:bg-[#F4F1EA]"
                    title="Play sample"
                    data-testid={`voicelab-play-${v.label.toLowerCase()}`}
                  >
                    {playing ? <Square size={14}/> : <Play size={14}/>}
                  </button>
                ) : (
                  <button
                    onClick={() => playing ? stop() : playLive(v.id, "openai")}
                    className="w-9 h-9 rounded-full bg-white border border-sand flex items-center justify-center text-[#59745D] hover:bg-[#F4F1EA]"
                    title="Generate live (free OpenAI)"
                  >
                    {playing ? <Square size={14}/> : (playingKey?.startsWith(`live-${v.id}`) ? <Loader2 size={14} className="animate-spin"/> : <Volume2 size={14}/>)}
                  </button>
                )}
                <button
                  onClick={() => save(tab, v.id)}
                  disabled={savingId === `${tab}-${v.id}` || picked}
                  className={`px-3 py-2 rounded-full text-xs font-medium ${picked ? "bg-[#59745D] text-white" : "bg-[#FDFBF7] border border-sand text-[#2D312E] hover:bg-white"} disabled:opacity-60`}
                  data-testid={`voicelab-save-${v.label.toLowerCase()}`}
                >
                  {picked ? "Active" : savingId === `${tab}-${v.id}` ? "…" : "Use this"}
                </button>
              </div>
            </li>
          );
        })}
      </ul>

      <p className="text-[11px] text-[#9A9F9D] leading-relaxed text-center pt-2">
        ElevenLabs samples were pre-generated. OpenAI plays live. Yaar will use this voice for chat replies, briefs, and reminder reads.
      </p>
    </div>
  );
}
