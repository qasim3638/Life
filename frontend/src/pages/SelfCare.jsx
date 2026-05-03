import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Container, Card, Eyebrow, PageHeader } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Sparkles, Heart, Trash2 } from "lucide-react";
import { toast } from "sonner";

const MOODS = [
  { v: 1, label: "heavy" },
  { v: 2, label: "low" },
  { v: 3, label: "steady" },
  { v: 4, label: "light" },
  { v: 5, label: "radiant" },
];

export default function SelfCare() {
  const [entries, setEntries] = useState([]);
  const [affirmations, setAffirmations] = useState([]);
  const [mood, setMood] = useState(3);
  const [gratitude, setGratitude] = useState(["", "", ""]);
  const [reflection, setReflection] = useState("");
  const [aiResp, setAiResp] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [todayAffirm, setTodayAffirm] = useState(null);

  const load = async () => {
    const [j, a] = await Promise.all([api.get("/journal-entries"), api.get("/affirmations")]);
    setEntries(j.data);
    setAffirmations(a.data);
    if (a.data.length) setTodayAffirm(a.data[Math.floor(Math.random() * a.data.length)]);
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    const grat = gratitude.filter(g => g.trim());
    if (!reflection.trim() && grat.length === 0) return toast.error("Write something — anything true.");
    try {
      await api.post("/journal-entries", {
        date: new Date().toISOString().slice(0, 10),
        mood, gratitude: grat, reflection,
      });
      toast.success("Kept safe.");
      setReflection(""); setGratitude(["", "", ""]); setMood(3);
      load();
    } catch { toast.error("Couldn't save"); }
  };

  const askAI = async () => {
    if (!reflection.trim()) return toast.error("Write your reflection first");
    setAiLoading(true);
    try {
      const { data } = await api.post("/ai/reflect", { prompt: reflection });
      setAiResp(data.text);
    } catch { toast.error("AI is resting"); }
    finally { setAiLoading(false); }
  };

  const remove = async (id) => {
    await api.delete(`/journal-entries/${id}`);
    load();
  };

  return (
    <Container>
      <PageHeader
        eyebrow="Self-love & reflection"
        title="Be gentle with the man you are becoming."
        subtitle="Write it down. Let the truth breathe outside of you for a while."
        image="https://static.prod-images.emergentagent.com/jobs/b8c548de-315f-4118-954b-1d59454f577f/images/089d41eba1d432a1fa65b246e0d0a157f3fd5d31d0135f2274dbded8c0379d43.png"
      />

      {todayAffirm && (
        <Card className="bg-[#F4F1EA] border-0 mb-8 text-center" data-testid="daily-affirmation">
          <Heart size={18} strokeWidth={1.5} className="text-[#C27A62] mx-auto" />
          <p className="font-serif text-2xl md:text-3xl text-[#2D312E] mt-3 leading-snug max-w-2xl mx-auto">
            {todayAffirm.text}
          </p>
          <p className="text-xs uppercase tracking-[0.3em] text-[#9A9F9D] mt-4">Today's affirmation</p>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Journal form */}
        <Card className="lg:col-span-2" data-testid="journal-form">
          <Eyebrow>Today's entry</Eyebrow>
          <h2 className="font-serif text-2xl text-[#2D312E] mb-5">How are you, really?</h2>

          <div className="mb-5">
            <p className="text-xs uppercase tracking-wider text-[#9A9F9D] mb-2">Mood</p>
            <div className="flex gap-2">
              {MOODS.map(m => (
                <button key={m.v}
                  onClick={() => setMood(m.v)}
                  className={`flex-1 py-2 rounded-full text-xs transition-colors ${
                    mood === m.v ? "bg-[#59745D] text-white" : "bg-[#F4F1EA] text-[#6B7270] hover:bg-sand"
                  }`}
                  data-testid={`mood-${m.v}`}
                >{m.label}</button>
              ))}
            </div>
          </div>

          <div className="mb-5">
            <p className="text-xs uppercase tracking-wider text-[#9A9F9D] mb-2">Three things I'm grateful for</p>
            <div className="space-y-2">
              {gratitude.map((g, i) => (
                <input key={i}
                  placeholder={`Gratitude ${i + 1}`}
                  value={g}
                  onChange={(e) => setGratitude(gratitude.map((x, idx) => idx === i ? e.target.value : x))}
                  className="w-full px-4 py-2.5 rounded-full bg-[#F4F1EA] border-0 text-sm text-[#2D312E] placeholder:text-[#9A9F9D] focus:ring-2 focus:ring-[#59745D] outline-none"
                  data-testid={`gratitude-${i}`}
                />
              ))}
            </div>
          </div>

          <div className="mb-5">
            <p className="text-xs uppercase tracking-wider text-[#9A9F9D] mb-2">Reflection</p>
            <Textarea
              placeholder="What's alive in you today?"
              value={reflection}
              onChange={(e) => setReflection(e.target.value)}
              rows={5}
              data-testid="reflection-input"
            />
          </div>

          <div className="flex gap-3">
            <Button onClick={save} className="rounded-full bg-[#59745D] hover:bg-[#4A604D]" data-testid="save-journal-btn">Keep this</Button>
            <Button variant="outline" onClick={askAI} disabled={aiLoading} className="rounded-full border-[#C27A62] text-[#C27A62] hover:bg-[#C27A62] hover:text-white" data-testid="ai-reflect-btn">
              <Sparkles size={14} className="mr-1" strokeWidth={1.5} /> {aiLoading ? "Listening…" : "Ask the coach"}
            </Button>
          </div>

          {aiResp && (
            <div className="mt-5 bg-[#F4F1EA] rounded-2xl p-5" data-testid="ai-reflection-response">
              <Eyebrow>A voice back to you</Eyebrow>
              <p className="font-serif text-lg text-[#2D312E] leading-relaxed mt-2">{aiResp}</p>
            </div>
          )}
        </Card>

        {/* Affirmations list */}
        <div>
          <Eyebrow>Affirmations</Eyebrow>
          <h2 className="font-serif text-2xl text-[#2D312E] mb-4">Return to these</h2>
          <div className="space-y-3">
            {affirmations.map(a => (
              <div key={a.id} className="bg-white rounded-2xl border border-sand p-4" data-testid={`affirm-${a.id}`}>
                <p className="font-serif text-base text-[#2D312E] leading-snug">"{a.text}"</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {entries.length > 0 && (
        <section className="mt-14">
          <Eyebrow>Your entries</Eyebrow>
          <h2 className="font-serif text-3xl text-[#2D312E] mb-5">The record of your becoming</h2>
          <div className="space-y-4">
            {entries.map(e => (
              <Card key={e.id} data-testid={`entry-${e.id}`}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-[#6B7270]">{e.date}</p>
                    <p className="text-xs uppercase tracking-wider text-[#C27A62] mt-1">
                      {MOODS.find(m => m.v === e.mood)?.label}
                    </p>
                  </div>
                  <button onClick={() => remove(e.id)} className="text-[#9A9F9D] hover:text-[#B85C50]"><Trash2 size={15} strokeWidth={1.5}/></button>
                </div>
                {e.gratitude?.length > 0 && (
                  <ul className="mt-3 text-sm text-[#2D312E] space-y-1">
                    {e.gratitude.map((g, i) => <li key={i}>· {g}</li>)}
                  </ul>
                )}
                {e.reflection && <p className="mt-3 text-[#2D312E] leading-relaxed">{e.reflection}</p>}
              </Card>
            ))}
          </div>
        </section>
      )}
    </Container>
  );
}
