import React, { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { Container, Card, Eyebrow, PageHeader } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Play, Pause, RotateCcw } from "lucide-react";

const PRESETS = [5, 10, 15, 20];

export default function Meditate() {
  const [meditations, setMeditations] = useState([]);
  const [duration, setDuration] = useState(600); // 10m
  const [remaining, setRemaining] = useState(600);
  const [running, setRunning] = useState(false);
  const [active, setActive] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    (async () => {
      const { data } = await api.get("/meditations");
      setMeditations(data);
    })();
  }, []);

  useEffect(() => {
    if (!running) return;
    intervalRef.current = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) { setRunning(false); return 0; }
        return r - 1;
      });
    }, 1000);
    return () => clearInterval(intervalRef.current);
  }, [running]);

  const setPreset = (min) => {
    setDuration(min * 60);
    setRemaining(min * 60);
    setRunning(false);
  };

  const mm = String(Math.floor(remaining / 60)).padStart(2, "0");
  const ss = String(remaining % 60).padStart(2, "0");

  return (
    <Container>
      <PageHeader
        eyebrow="Come back to yourself"
        title="Breathe. Then begin again."
        subtitle="A few moments of stillness is not time lost. It is the only time you truly live."
        image="https://images.unsplash.com/photo-1764192114257-ae9ecf97eb6f"
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Timer */}
        <Card className="flex flex-col items-center py-14 bg-[#F4F1EA] border-0 relative overflow-hidden" data-testid="meditation-timer-card">
          <div className="relative">
            <div className="breath-ring absolute inset-0 rounded-full bg-[#59745D]/20 blur-2xl" />
            <div className="relative w-56 h-56 rounded-full flex items-center justify-center bg-white border border-sand shadow-sm">
              <div className="text-center">
                <p className="font-serif text-6xl text-[#2D312E] tracking-tight">{mm}:{ss}</p>
                <p className="text-xs uppercase tracking-[0.3em] text-[#9A9F9D] mt-2">
                  {running ? "Breathing" : remaining === 0 ? "Complete" : "Ready"}
                </p>
              </div>
            </div>
          </div>

          <div className="flex gap-2 mt-8">
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
            <Button
              onClick={() => setRunning(r => !r)}
              className="rounded-full bg-[#59745D] hover:bg-[#4A604D] px-8"
              data-testid="meditation-toggle-btn"
            >
              {running ? <><Pause size={15} className="mr-1" /> Pause</> : <><Play size={15} className="mr-1" /> Start</>}
            </Button>
            <Button
              variant="outline"
              onClick={() => { setRemaining(duration); setRunning(false); }}
              className="rounded-full border-[#6B7270] text-[#6B7270]"
              data-testid="meditation-reset-btn"
            >
              <RotateCcw size={15} className="mr-1" /> Reset
            </Button>
          </div>
          <p className="text-sm text-[#6B7270] mt-6 max-w-xs text-center leading-relaxed">
            Inhale four counts. Hold four. Exhale four. Hold four. Repeat.
          </p>
        </Card>

        {/* Library */}
        <div>
          <Eyebrow>Guided sessions</Eyebrow>
          <h2 className="font-serif text-3xl text-[#2D312E] mb-5">When you need a voice</h2>
          {active && (
            <div className="aspect-video mb-5 rounded-3xl overflow-hidden border border-sand">
              <iframe
                src={`https://www.youtube.com/embed/${active}?autoplay=1&rel=0`}
                title="Guided meditation" allow="autoplay; encrypted-media" allowFullScreen
                className="w-full h-full"
              />
            </div>
          )}
          <div className="space-y-3">
            {meditations.map(m => (
              <button
                key={m.id}
                onClick={() => setActive(m.youtube_id)}
                className={`w-full text-left bg-white rounded-2xl border border-sand p-4 flex items-center gap-4 hover:-translate-y-0.5 transition-all ${
                  active === m.youtube_id ? "ring-2 ring-[#59745D]" : ""
                }`}
                data-testid={`meditation-${m.id}`}
              >
                <img src={`https://i.ytimg.com/vi/${m.youtube_id}/default.jpg`} alt="" className="w-20 h-14 object-cover rounded-xl"/>
                <div className="flex-1">
                  <p className="text-[11px] uppercase tracking-widest text-[#C27A62]">{m.category} · {m.duration}</p>
                  <p className="font-serif text-lg text-[#2D312E] leading-tight">{m.title}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </Container>
  );
}
