import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { sendToCompanion } from "../lib/companion";
import { Container, Card, Eyebrow, PageHeader } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Plus, Trash2, Trophy, RefreshCcw, Sparkles, Heart, MessageCircle } from "lucide-react";
import { toast } from "sonner";

function useTicker() {
  const [, set] = useState(0);
  useEffect(() => {
    const id = setInterval(() => set((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);
}

function streakParts(startedClean) {
  if (!startedClean) return { d: 0, h: 0, m: 0, s: 0, totalDays: 0 };
  const start = new Date(startedClean).getTime();
  const ms = Date.now() - start;
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const d = Math.floor(totalSec / 86400);
  const h = Math.floor((totalSec % 86400) / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  return { d, h, m, s, totalDays: d };
}

export default function Sobriety() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", notes: "" });
  useTicker();

  const load = async () => {
    const { data } = await api.get("/addictions");
    setItems(data);
  };
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!form.name.trim()) return toast.error("Name it");
    await api.post("/addictions", form);
    setOpen(false);
    setForm({ name: "", notes: "" });
    load();
    toast.success("The clock starts now.");
  };

  return (
    <Container>
      <PageHeader
        eyebrow="Sobriety & habits"
        title="Honest with yourself. Gentle with yourself."
        subtitle="Some days you stay. Some days you slip. Both are part of the work."
      />

      <div className="flex justify-end mb-6">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="rounded-full bg-[#59745D] hover:bg-[#4A604D]" data-testid="add-addiction-btn">
              <Plus size={14} className="mr-1"/> Track a habit
            </Button>
          </DialogTrigger>
          <DialogContent className="rounded-3xl">
            <DialogHeader><DialogTitle className="font-serif text-2xl">Begin a clock</DialogTitle></DialogHeader>
            <div className="space-y-3 mt-2">
              <Input value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} placeholder="Name (e.g., late-night scrolling)" data-testid="addiction-name-input"/>
              <Textarea value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})} placeholder="Why you want to stop. What you'll gain instead." rows={3}/>
              <Button onClick={add} className="w-full rounded-full bg-[#59745D]" data-testid="save-addiction-btn">Start the clock</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {items.length === 0 ? (
        <Card className="text-center py-16" data-testid="sobriety-empty">
          <p className="font-serif text-2xl text-[#2D312E]">No habits being tracked yet.</p>
          <p className="text-[#6B7270] mt-2">Naming the thing is the first kindness.</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {items.map(a => <AddictionCard key={a.id} item={a} reload={load}/>)}
        </div>
      )}
    </Container>
  );
}

function AddictionCard({ item, reload }) {
  const [slipOpen, setSlipOpen] = useState(false);
  const [slipNote, setSlipNote] = useState("");
  const [supportOpen, setSupportOpen] = useState(false);
  const [supportText, setSupportText] = useState("");
  const [supportLoading, setSupportLoading] = useState(false);
  const [slips, setSlips] = useState([]);
  const [showSlips, setShowSlips] = useState(false);
  const navigate = useNavigate();

  const { d, h, m, s, totalDays } = streakParts(item.started_clean);

  const slip = async () => {
    await api.post(`/addictions/${item.id}/slip`, { note: slipNote });
    setSlipOpen(false);
    setSlipNote("");
    reload();
    toast.success("Logged. The clock starts again. You're still here.");
  };

  const remove = async () => {
    if (!window.confirm(`Stop tracking "${item.name}"?`)) return;
    await api.delete(`/addictions/${item.id}`);
    reload();
  };

  const support = async () => {
    setSupportOpen(true); setSupportText(""); setSupportLoading(true);
    try {
      const { data } = await api.post(`/ai/sobriety-support/${item.id}`, {});
      setSupportText(data.text);
    } catch { toast.error("AI is resting"); }
    finally { setSupportLoading(false); }
  };

  const loadSlips = async () => {
    setShowSlips(!showSlips);
    if (!showSlips) {
      const { data } = await api.get(`/addictions/${item.id}/slips`);
      setSlips(data);
    }
  };

  const talkToCompanion = async () => {
    const msg = `I want to talk about staying free from ${item.name}. I've been clean ${totalDays} days. My longest was ${Math.max(item.longest_streak_days || 0, totalDays)} days. ${item.notes ? `Why I want this: ${item.notes}.` : ""} Can you help me think this through?`;
    try {
      await sendToCompanion(msg, navigate);
    } catch { toast.error("Couldn't reach the companion"); }
  };

  const isLongest = totalDays >= (item.longest_streak_days || 0) && totalDays > 0;

  return (
    <Card data-testid={`addiction-${item.id}`} className="relative overflow-hidden">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <Eyebrow>Free of</Eyebrow>
          <h3 className="font-serif text-2xl text-[#2D312E] mt-1 leading-tight">{item.name}</h3>
          {item.notes && <p className="text-sm text-[#6B7270] mt-1 leading-relaxed">{item.notes}</p>}
        </div>
        <button onClick={remove} className="text-[#9A9F9D] hover:text-[#B85C50] shrink-0" data-testid={`del-addiction-${item.id}`}><Trash2 size={14} strokeWidth={1.5}/></button>
      </div>

      <div className="my-6 grid grid-cols-4 gap-2 text-center bg-[#F4F1EA] rounded-2xl py-5">
        {[
          { val: d, label: "days" },
          { val: h, label: "hours" },
          { val: m, label: "min" },
          { val: s, label: "sec" },
        ].map((u, i) => (
          <div key={i}>
            <p className="font-serif text-3xl md:text-4xl text-[#2D312E] tabular-nums">{String(u.val).padStart(2, "0")}</p>
            <p className="text-[10px] uppercase tracking-widest text-[#9A9F9D] mt-1">{u.label}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3 text-sm text-[#6B7270]">
        <span className="flex items-center gap-1">
          <Trophy size={13} strokeWidth={1.5} className={isLongest ? "text-[#C27A62]" : "text-[#9A9F9D]"}/>
          longest: {Math.max(item.longest_streak_days || 0, totalDays)} days
        </span>
        <span className="flex items-center gap-1">
          <RefreshCcw size={12} strokeWidth={1.5} className="text-[#9A9F9D]"/>
          resets: {item.reset_count || 0}
        </span>
      </div>

      <div className="flex flex-wrap gap-2 mt-5">
        <Button size="sm" onClick={support} variant="outline" className="rounded-full border-[#59745D] text-[#59745D] hover:bg-[#59745D] hover:text-white" data-testid={`support-${item.id}`}>
          <Sparkles size={13} strokeWidth={1.5} className="mr-1"/> Encouragement
        </Button>
        <Button size="sm" onClick={talkToCompanion} variant="outline" className="rounded-full border-[#A3897C] text-[#A3897C] hover:bg-[#A3897C] hover:text-white" data-testid={`talk-${item.id}`}>
          <MessageCircle size={13} strokeWidth={1.5} className="mr-1"/> Talk it through
        </Button>
        <Button size="sm" onClick={() => setSlipOpen(true)} variant="ghost" className="rounded-full text-[#9A9F9D] hover:text-[#B85C50]" data-testid={`slip-${item.id}`}>
          <Heart size={13} strokeWidth={1.5} className="mr-1"/> I slipped
        </Button>
        <button onClick={loadSlips} className="text-xs text-[#9A9F9D] hover:text-[#6B7270] ml-auto self-center" data-testid={`history-${item.id}`}>
          {showSlips ? "Hide history" : `History (${item.reset_count || 0})`}
        </button>
      </div>

      {showSlips && (
        <div className="mt-4 pt-4 border-t border-sand">
          <Eyebrow>Slip history</Eyebrow>
          {slips.length === 0 ? (
            <p className="text-sm text-[#9A9F9D] italic mt-1">No slips logged.</p>
          ) : (
            <ul className="mt-2 space-y-2">
              {slips.map(s => (
                <li key={s.id} className="text-sm">
                  <p className="text-[#2D312E]">{new Date(s.at).toLocaleDateString()} · {s.streak_days_before}d streak before</p>
                  {s.note && <p className="text-[#6B7270] text-xs mt-0.5">{s.note}</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Slip dialog */}
      <Dialog open={slipOpen} onOpenChange={setSlipOpen}>
        <DialogContent className="rounded-3xl">
          <DialogHeader><DialogTitle className="font-serif text-2xl">A slip is data, not a sentence.</DialogTitle></DialogHeader>
          <Textarea
            value={slipNote}
            onChange={(e) => setSlipNote(e.target.value)}
            placeholder="What was happening? What did you feel? (optional)"
            rows={3}
            data-testid={`slip-note-${item.id}`}
          />
          <Button onClick={slip} className="w-full rounded-full bg-[#A3897C] hover:bg-[#8C7367] mt-2" data-testid={`slip-confirm-${item.id}`}>Log it. Begin again.</Button>
        </DialogContent>
      </Dialog>

      {/* Support dialog */}
      <Dialog open={supportOpen} onOpenChange={setSupportOpen}>
        <DialogContent className="rounded-3xl">
          <DialogHeader><DialogTitle className="font-serif text-2xl">A word from your companion</DialogTitle></DialogHeader>
          {supportLoading ? (
            <p className="text-[#6B7270]">Listening to your effort…</p>
          ) : (
            <p className="font-serif text-lg text-[#2D312E] leading-relaxed whitespace-pre-wrap">{supportText}</p>
          )}
        </DialogContent>
      </Dialog>
    </Card>
  );
}
