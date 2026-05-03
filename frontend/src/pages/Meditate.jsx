import React, { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { Container, Card, Eyebrow, PageHeader } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Play, Pause, RotateCcw } from "lucide-react";
import { usePlayer } from "../components/Player";
import { YouTubeThumb, WatchOnYouTube } from "../components/YouTubeThumb";

const PRESETS = [5, 10, 15, 20];
const CATEGORIES = [
  { key: "Guided", label: "Guided" },
  { key: "Wisdom Story", label: "Wisdom Stories" },
  { key: "Sleep Story", label: "Sleep Stories" },
  { key: "Meditation Music", label: "Music & Sound" },
];

export default function Meditate() {
  const [guided, setGuided] = useState([]);
  const [audio, setAudio] = useState([]);
  const [tab, setTab] = useState("Guided");
  const [duration, setDuration] = useState(600);
  const [remaining, setRemaining] = useState(600);
  const [running, setRunning] = useState(false);
  const intervalRef = useRef(null);
  const player = usePlayer();

  const playChime = () => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const tones = [523.25, 659.25, 783.99];
      tones.forEach((freq, i) => {
        const o = ctx.createOscillator();
        const g = ctx.createGain();
        o.type = "sine";
        o.frequency.value = freq;
        o.connect(g); g.connect(ctx.destination);
        const start = ctx.currentTime + i * 0.15;
        g.gain.setValueAtTime(0, start);
        g.gain.linearRampToValueAtTime(0.25, start + 0.05);
        g.gain.exponentialRampToValueAtTime(0.001, start + 2.5);
        o.start(start);
        o.stop(start + 2.6);
      });
    } catch (e) { /* silent */ }
  };

  useEffect(() => {
    (async () => {
      const [g, a] = await Promise.all([api.get("/meditations"), api.get("/audio")]);
      setGuided(g.data);
      setAudio(a.data);
    })();
  }, []);

  useEffect(() => {
    if (!running) return;
    intervalRef.current = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) { setRunning(false); playChime(); return 0; }
        return r - 1;
      });
    }, 1000);
    return () => clearInterval(intervalRef.current);
  }, [running]);

  const setPreset = (min) => {
    setDuration(min * 60); setRemaining(min * 60); setRunning(false);
  };

  const mm = String(Math.floor(remaining / 60)).padStart(2, "0");
  const ss = String(remaining % 60).padStart(2, "0");

  const items = tab === "Guided"
    ? guided.map(m => ({ ...m, category: "Guided" }))
    : audio.filter(a => a.category === tab);

  return (
    <Container>
      <PageHeader
        eyebrow="Come back to yourself"
        title="Breathe. Listen. Begin again."
        subtitle="A timer for stillness. Stories for wisdom. Sounds for sleep. Music for the in-between."
        image="https://images.unsplash.com/photo-1764192114257-ae9ecf97eb6f"
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-10">
        {/* Timer */}
        <Card className="flex flex-col items-center py-12 bg-[#F4F1EA] border-0 relative overflow-hidden" data-testid="meditation-timer-card">
          <div className="relative">
            <div className="breath-ring absolute inset-0 rounded-full bg-[#59745D]/20 blur-2xl"/>
            <div className="relative w-52 h-52 rounded-full flex items-center justify-center bg-white border border-sand shadow-sm">
              <div className="text-center">
                <p className="font-serif text-6xl text-[#2D312E] tracking-tight">{mm}:{ss}</p>
                <p className="text-xs uppercase tracking-[0.3em] text-[#9A9F9D] mt-2">
                  {running ? "Breathing" : remaining === 0 ? "Complete" : "Ready"}
                </p>
              </div>
            </div>
          </div>
          <div className="flex gap-2 mt-7">
            {PRESETS.map(m => (
              <button key={m} onClick={() => setPreset(m)}
                className={`px-4 py-1.5 rounded-full text-sm transition-colors ${
                  duration === m * 60 ? "bg-[#59745D] text-white" : "bg-white border border-sand text-[#6B7270] hover:bg-sand"
                }`}
                data-testid={`preset-${m}`}
              >{m} min</button>
            ))}
          </div>
          <div className="flex gap-3 mt-5">
            <Button onClick={() => setRunning(r => !r)} className="rounded-full bg-[#59745D] hover:bg-[#4A604D] px-8" data-testid="meditation-toggle-btn">
              {running ? <><Pause size={15} className="mr-1"/> Pause</> : <><Play size={15} className="mr-1"/> Start</>}
            </Button>
            <Button variant="outline" onClick={() => { setRemaining(duration); setRunning(false); }} className="rounded-full border-[#6B7270] text-[#6B7270]" data-testid="meditation-reset-btn">
              <RotateCcw size={15} className="mr-1"/> Reset
            </Button>
          </div>
          <p className="text-sm text-[#6B7270] mt-6 max-w-xs text-center leading-relaxed">
            Inhale four counts. Hold four. Exhale four. Hold four.
          </p>
        </Card>

        <div>
          <Eyebrow>The library</Eyebrow>
          <h2 className="font-serif text-3xl text-[#2D312E] mb-1">Listen anywhere</h2>
          <p className="text-sm text-[#6B7270] mb-5 leading-relaxed">
            Play any track and keep browsing — a small floating player keeps it with you.
          </p>
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map(c => (
              <button key={c.key} onClick={() => setTab(c.key)}
                className={`px-4 py-1.5 rounded-full text-xs uppercase tracking-wider transition-colors ${
                  tab === c.key ? "bg-[#59745D] text-white" : "bg-[#F4F1EA] text-[#6B7270] hover:bg-sand"
                }`}
                data-testid={`audio-tab-${c.key}`}
              >{c.label}</button>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {items.map(item => (
          <Card key={item.id} className="p-0 overflow-hidden cursor-pointer group" onClick={() => player.play({ youtube_id: item.youtube_id, title: item.title, category: item.category })} data-testid={`audio-${item.id}`}>
            <div className="aspect-video relative">
              <YouTubeThumb youtubeId={item.youtube_id} title={item.title} className="absolute inset-0" />
              <div className="absolute inset-0 bg-black/40 group-hover:bg-black/30 transition-colors flex items-center justify-center">
                <div className="w-14 h-14 rounded-full bg-white/90 flex items-center justify-center group-hover:scale-110 transition-transform">
                  <Play size={20} strokeWidth={1.5} className="ml-0.5 text-[#2D312E]"/>
                </div>
              </div>
            </div>
            <div className="p-4">
              <p className="text-[10px] uppercase tracking-widest text-[#C27A62]">{item.category} · {item.duration}</p>
              <h3 className="font-serif text-lg text-[#2D312E] mt-0.5 leading-tight">{item.title}</h3>
              {item.description && <p className="text-xs text-[#6B7270] mt-1 line-clamp-2">{item.description}</p>}
              <div className="mt-2">
                <WatchOnYouTube youtubeId={item.youtube_id} />
              </div>
            </div>
          </Card>
        ))}
        {items.length === 0 && (
          <p className="md:col-span-2 lg:col-span-3 text-center text-[#6B7270] py-10">Nothing yet in this section.</p>
        )}
      </div>
    </Container>
  );
}
