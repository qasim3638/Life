import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { sendToCompanion } from "../lib/companion";
import { Container, Card, Eyebrow, PageHeader } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Play, Pause, RotateCcw, Sparkles, Zap, Timer, AlertCircle, MessageCircle } from "lucide-react";
import { toast } from "sonner";

const TRIGGERS = ["phone", "notification", "browser", "hunger", "thought", "person", "fatigue", "other"];

export default function Focus() {
  const [task, setTask] = useState("");
  const [planned, setPlanned] = useState(25);
  const [remaining, setRemaining] = useState(25 * 60);
  const [running, setRunning] = useState(false);
  const [sessionStart, setSessionStart] = useState(null);
  const [stats, setStats] = useState({ today_focus_min: 0, today_sessions: 0, today_completed_sessions: 0, today_distractions: 0 });
  const [recentDistractions, setRecentDistractions] = useState([]);
  const [recentSessions, setRecentSessions] = useState([]);
  const [distractionOpen, setDistractionOpen] = useState(false);
  const [distractionForm, setDistractionForm] = useState({ trigger: "phone", note: "" });
  const [aiText, setAiText] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const intervalRef = useRef(null);
  const navigate = useNavigate();

  const refresh = async () => {
    const [s, d, ss] = await Promise.all([
      api.get("/focus-stats"),
      api.get("/distractions"),
      api.get("/focus-sessions"),
    ]);
    setStats(s.data);
    setRecentDistractions(d.data);
    setRecentSessions(ss.data);
  };
  useEffect(() => { refresh(); }, []);

  useEffect(() => { setRemaining(planned * 60); }, [planned]);

  const playChime = () => {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      [659.25, 783.99].forEach((freq, i) => {
        const o = ctx.createOscillator(); const g = ctx.createGain();
        o.type = "sine"; o.frequency.value = freq;
        o.connect(g); g.connect(ctx.destination);
        const start = ctx.currentTime + i * 0.18;
        g.gain.setValueAtTime(0, start);
        g.gain.linearRampToValueAtTime(0.25, start + 0.04);
        g.gain.exponentialRampToValueAtTime(0.001, start + 1.4);
        o.start(start); o.stop(start + 1.5);
      });
    } catch {}
  };

  const finishSession = async (completed) => {
    setRunning(false);
    const actual = completed ? planned : Math.max(0, Math.round((planned * 60 - remaining) / 60));
    if (actual > 0 || completed) {
      await api.post("/focus-sessions", { task, planned_min: planned, actual_min: actual, completed });
    }
    if (completed) playChime();
    setSessionStart(null);
    setRemaining(planned * 60);
    refresh();
  };

  useEffect(() => {
    if (!running) return;
    intervalRef.current = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) { finishSession(true); return 0; }
        return r - 1;
      });
    }, 1000);
    return () => clearInterval(intervalRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running]);

  const startToggle = () => {
    if (!running && !sessionStart) setSessionStart(Date.now());
    setRunning(r => !r);
  };

  const reset = () => {
    if (running) finishSession(false);
    else { setRemaining(planned * 60); setSessionStart(null); }
  };

  const logDistraction = async () => {
    await api.post("/distractions", distractionForm);
    setDistractionOpen(false);
    setDistractionForm({ trigger: "phone", note: "" });
    refresh();
    toast.success("Logged. No judgment.");
  };

  const askAI = async () => {
    setAiLoading(true);
    try {
      const { data } = await api.post("/ai/focus-tips", {});
      setAiText(data.text);
    } catch { toast.error("AI is resting"); }
    finally { setAiLoading(false); }
  };

  const talkToCompanion = async () => {
    const top = recentDistractions.slice(0, 5).map(d => `${d.trigger}${d.note ? `: ${d.note}` : ""}`);
    const msg = `I'm struggling with focus today. Today: ${stats.today_focus_min} min focused, ${stats.today_distractions} distractions. Recent triggers: ${top.join("; ") || "none logged"}. Can you help me think this through?`;
    try {
      await sendToCompanion(msg, navigate);
    } catch { toast.error("Couldn't reach the companion"); }
  };

  const mm = String(Math.floor(remaining / 60)).padStart(2, "0");
  const ss = String(remaining % 60).padStart(2, "0");
  const pct = 1 - remaining / (planned * 60 || 1);

  return (
    <Container>
      <PageHeader
        eyebrow="Time & attention"
        title="Protect what's most fragile: your focus."
        subtitle="One task. One block. Then you can rest. The trick is starting."
      />

      <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-6 mb-8">
        {/* Timer */}
        <Card className="bg-[#F4F1EA] border-0" data-testid="focus-timer">
          <Eyebrow>Focus block</Eyebrow>
          <Input
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="What is the one task?"
            className="bg-white mt-3"
            data-testid="focus-task-input"
          />
          <div className="flex items-center justify-center my-7">
            <div className="relative w-56 h-56">
              <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                <circle cx="50" cy="50" r="44" stroke="#E8E2D2" strokeWidth="4" fill="none"/>
                <circle cx="50" cy="50" r="44" stroke="#59745D" strokeWidth="4" fill="none"
                  strokeLinecap="round" strokeDasharray={2 * Math.PI * 44}
                  strokeDashoffset={2 * Math.PI * 44 * (1 - pct)}
                  style={{ transition: "stroke-dashoffset 0.6s ease" }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <p className="font-serif text-6xl text-[#2D312E]">{mm}:{ss}</p>
                <p className="text-xs uppercase tracking-[0.3em] text-[#9A9F9D] mt-1">
                  {running ? "Focused" : remaining === 0 ? "Done" : "Ready"}
                </p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-3">
            {[15, 25, 45, 60].map(m => (
              <button key={m} onClick={() => setPlanned(m)} disabled={running}
                className={`px-3 py-1 rounded-full text-xs ${planned === m ? "bg-[#59745D] text-white" : "bg-white border border-sand text-[#6B7270]"}`}
                data-testid={`focus-preset-${m}`}
              >{m} min</button>
            ))}
          </div>
          <div className="flex items-center justify-center gap-3 mt-5">
            <Button onClick={startToggle} className="rounded-full bg-[#59745D] hover:bg-[#4A604D] px-7" data-testid="focus-toggle">
              {running ? <><Pause size={15} className="mr-1"/> Pause</> : <><Play size={15} className="mr-1"/> Begin</>}
            </Button>
            <Button onClick={reset} variant="outline" className="rounded-full border-[#6B7270] text-[#6B7270]" data-testid="focus-reset">
              <RotateCcw size={15} className="mr-1"/> {running ? "End" : "Reset"}
            </Button>
            <Button onClick={() => setDistractionOpen(true)} variant="outline" className="rounded-full border-[#C27A62] text-[#C27A62] hover:bg-[#C27A62] hover:text-white" data-testid="focus-distract">
              <AlertCircle size={15} className="mr-1"/> Got distracted
            </Button>
          </div>
        </Card>

        {/* Today stats */}
        <div className="space-y-4">
          <Card data-testid="focus-stats-card">
            <Eyebrow>Today</Eyebrow>
            <div className="grid grid-cols-2 gap-5 mt-3">
              <div>
                <p className="font-serif text-5xl text-[#2D312E]">{stats.today_focus_min}</p>
                <p className="text-xs text-[#6B7270] mt-1">minutes focused</p>
              </div>
              <div>
                <p className="font-serif text-5xl text-[#2D312E]">{stats.today_completed_sessions}</p>
                <p className="text-xs text-[#6B7270] mt-1">sessions completed</p>
              </div>
              <div>
                <p className="font-serif text-5xl text-[#C27A62]">{stats.today_distractions}</p>
                <p className="text-xs text-[#6B7270] mt-1">distractions noted</p>
              </div>
              <div>
                <p className="font-serif text-5xl text-[#2D312E]">{stats.today_sessions}</p>
                <p className="text-xs text-[#6B7270] mt-1">sessions started</p>
              </div>
            </div>
          </Card>
          <Card data-testid="focus-tips-card">
            <Eyebrow>AI focus coach</Eyebrow>
            {aiText ? (
              <p className="font-serif text-base text-[#2D312E] mt-2 leading-relaxed whitespace-pre-wrap">{aiText}</p>
            ) : (
              <p className="text-sm text-[#6B7270] mt-2 leading-relaxed">
                Get specific tips drawn from your last 7 days of distractions.
              </p>
            )}
            <Button onClick={askAI} disabled={aiLoading} variant="outline" size="sm"
              className="rounded-full border-[#C27A62] text-[#C27A62] hover:bg-[#C27A62] hover:text-white mt-3"
              data-testid="focus-ai-btn"
            >
              <Sparkles size={13} className="mr-1" strokeWidth={1.5}/>
              {aiLoading ? "Thinking…" : aiText ? "Refresh" : "Get tips"}
            </Button>
            <Button onClick={talkToCompanion} variant="ghost" size="sm"
              className="rounded-full text-[#59745D] hover:bg-[#F4F1EA] mt-3 ml-2"
              data-testid="focus-talk-btn"
            >
              <MessageCircle size={13} className="mr-1" strokeWidth={1.5}/> Talk to companion
            </Button>
          </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent distractions */}
        <Card data-testid="distractions-list">
          <div className="flex items-center gap-2 mb-3">
            <Zap size={16} strokeWidth={1.5} className="text-[#C27A62]"/>
            <Eyebrow>Recent distractions</Eyebrow>
          </div>
          {recentDistractions.length === 0 ? (
            <p className="text-sm text-[#9A9F9D] italic">None yet. The day is young.</p>
          ) : (
            <ul className="space-y-2">
              {recentDistractions.slice(0, 8).map(d => (
                <li key={d.id} className="text-sm text-[#2D312E] bg-[#F4F1EA] rounded-xl px-3 py-2 flex items-center justify-between">
                  <span><span className="text-[10px] uppercase tracking-widest text-[#C27A62] mr-2">{d.trigger}</span>{d.note || "—"}</span>
                  <span className="text-xs text-[#9A9F9D]">{new Date(d.at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Recent sessions */}
        <Card data-testid="sessions-list">
          <div className="flex items-center gap-2 mb-3">
            <Timer size={16} strokeWidth={1.5} className="text-[#59745D]"/>
            <Eyebrow>Recent sessions</Eyebrow>
          </div>
          {recentSessions.length === 0 ? (
            <p className="text-sm text-[#9A9F9D] italic">No sessions yet.</p>
          ) : (
            <ul className="space-y-2">
              {recentSessions.slice(0, 8).map(s => (
                <li key={s.id} className="text-sm text-[#2D312E] bg-white border border-sand rounded-xl px-3 py-2 flex items-center justify-between">
                  <span><span className={`text-[10px] uppercase tracking-widest mr-2 ${s.completed ? "text-[#59745D]" : "text-[#9A9F9D]"}`}>{s.completed ? "completed" : "ended"}</span>{s.task || "—"}</span>
                  <span className="text-xs text-[#6B7270]">{s.actual_min}/{s.planned_min} min</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* Distraction dialog */}
      <Dialog open={distractionOpen} onOpenChange={setDistractionOpen}>
        <DialogContent className="rounded-3xl">
          <DialogHeader><DialogTitle className="font-serif text-2xl">What pulled you?</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <Select value={distractionForm.trigger} onValueChange={(v) => setDistractionForm({...distractionForm, trigger: v})}>
              <SelectTrigger data-testid="distract-trigger-select"><SelectValue/></SelectTrigger>
              <SelectContent>{TRIGGERS.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
            </Select>
            <Input
              value={distractionForm.note}
              onChange={(e) => setDistractionForm({...distractionForm, note: e.target.value})}
              placeholder="Note (optional) — just a few words"
              data-testid="distract-note-input"
            />
            <Button onClick={logDistraction} className="w-full rounded-full bg-[#59745D]" data-testid="distract-save-btn">Log it. No judgment.</Button>
          </div>
        </DialogContent>
      </Dialog>
    </Container>
  );
}
