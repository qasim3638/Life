import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Container, Card, Eyebrow, PageHeader } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Plus, Trash2, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

const CATEGORIES = ["Health", "Career", "Family", "Spiritual", "Financial", "Adventure", "Learning", "Legacy"];
const STATUSES = [
  { key: "planned", label: "Planted" },
  { key: "in_progress", label: "Tending" },
  { key: "achieved", label: "Bloomed" },
];

const START_YEAR = new Date().getFullYear();
const AGE_NOW = 40;

export default function Blueprint() {
  const [goals, setGoals] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    year: START_YEAR + 1, age: AGE_NOW + 1, category: "Health", title: "", description: "",
  });

  const load = async () => {
    const { data } = await api.get("/life-goals");
    setGoals(data);
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.title.trim()) return toast.error("Give your goal a name");
    try {
      await api.post("/life-goals", form);
      toast.success("Goal planted in your blueprint");
      setOpen(false);
      setForm({ year: START_YEAR + 1, age: AGE_NOW + 1, category: "Health", title: "", description: "" });
      load();
    } catch {
      toast.error("Couldn't save");
    }
  };

  const cycleStatus = async (g) => {
    const order = ["planned", "in_progress", "achieved"];
    const next = order[(order.indexOf(g.status) + 1) % order.length];
    await api.put(`/life-goals/${g.id}`, { ...g, status: next });
    load();
  };

  const remove = async (id) => {
    await api.delete(`/life-goals/${id}`);
    load();
  };

  // Group goals by 5-year decades
  const decades = [];
  for (let age = AGE_NOW; age < 80; age += 5) {
    decades.push({ ageStart: age, ageEnd: age + 4, year: START_YEAR + (age - AGE_NOW) });
  }

  const goalsByAge = goals.reduce((acc, g) => {
    (acc[g.age] = acc[g.age] || []).push(g);
    return acc;
  }, {});

  return (
    <Container>
      <PageHeader
        eyebrow="The long view"
        title="Forty years. One honest arc."
        subtitle="Plant goals across the decades. Tend them when ready. Watch them bloom in time."
        image="https://static.prod-images.emergentagent.com/jobs/b8c548de-315f-4118-954b-1d59454f577f/images/252006b3fbe027b3d88a8673d327c4616289615eec678e0bbb491a6b1e1f603e.png"
      />

      <div className="flex items-center justify-between mb-6">
        <p className="text-sm text-[#6B7270]">{goals.length} goals across your timeline</p>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="rounded-full bg-[#59745D] hover:bg-[#4A604D]" data-testid="add-goal-btn">
              <Plus size={16} strokeWidth={1.5} className="mr-1" /> Plant a goal
            </Button>
          </DialogTrigger>
          <DialogContent className="rounded-3xl">
            <DialogHeader><DialogTitle className="font-serif text-2xl">Plant a life goal</DialogTitle></DialogHeader>
            <div className="space-y-4 mt-2">
              <Input
                placeholder="Goal title (e.g. Run a half-marathon)"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                data-testid="goal-title-input"
              />
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-[#9A9F9D] uppercase tracking-wider">Target age</label>
                  <Input type="number" min={AGE_NOW} max={80}
                    value={form.age}
                    onChange={(e) => setForm({ ...form, age: parseInt(e.target.value), year: START_YEAR + (parseInt(e.target.value) - AGE_NOW) })}
                    data-testid="goal-age-input"
                  />
                </div>
                <div>
                  <label className="text-xs text-[#9A9F9D] uppercase tracking-wider">Category</label>
                  <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                    <SelectTrigger data-testid="goal-category-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {CATEGORIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Textarea
                placeholder="Why does this matter? How will you know you've arrived?"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                data-testid="goal-description-input"
              />
              <Button onClick={save} className="w-full rounded-full bg-[#59745D]" data-testid="goal-save-btn">Plant goal</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="space-y-10">
        {decades.map(({ ageStart, ageEnd, year }) => {
          const range = [];
          for (let a = ageStart; a <= ageEnd; a++) range.push(a);
          const count = range.reduce((s, a) => s + (goalsByAge[a]?.length || 0), 0);
          return (
            <section key={ageStart} className="relative" data-testid={`decade-${ageStart}`}>
              <div className="sticky top-0 z-10 bg-[#FDFBF7]/90 backdrop-blur py-3 mb-4 border-b border-sand flex items-baseline justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.3em] text-[#9A9F9D]">Age {ageStart}–{ageEnd}</p>
                  <h2 className="font-serif text-3xl text-[#2D312E]">{year}–{year + 4}</h2>
                </div>
                <p className="text-xs text-[#6B7270]">{count} goal{count !== 1 ? "s" : ""}</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {range.flatMap(age => (goalsByAge[age] || []).map(g => (
                  <Card key={g.id} data-testid={`goal-${g.id}`} className="relative group">
                    <div className="flex items-center justify-between">
                      <span className="text-xs tracking-wider uppercase text-[#C27A62]">{g.category}</span>
                      <span className="text-xs text-[#9A9F9D]">Age {g.age}</span>
                    </div>
                    <h3 className="font-serif text-xl text-[#2D312E] mt-2">{g.title}</h3>
                    {g.description && <p className="text-sm text-[#6B7270] mt-2 leading-relaxed">{g.description}</p>}
                    <div className="mt-4 flex items-center justify-between">
                      <button
                        onClick={() => cycleStatus(g)}
                        className={`text-xs px-3 py-1 rounded-full transition-colors ${
                          g.status === "achieved" ? "bg-[#59745D] text-white" :
                          g.status === "in_progress" ? "bg-[#C27A62] text-white" :
                          "bg-[#F4F1EA] text-[#6B7270]"
                        }`}
                        data-testid={`goal-status-${g.id}`}
                      >
                        {STATUSES.find(s => s.key === g.status)?.label}
                      </button>
                      <button onClick={() => remove(g.id)} className="text-[#9A9F9D] hover:text-[#B85C50]" data-testid={`goal-delete-${g.id}`}>
                        <Trash2 size={15} strokeWidth={1.5} />
                      </button>
                    </div>
                    {g.status === "achieved" && (
                      <CheckCircle2 size={16} strokeWidth={1.5} className="absolute top-5 right-5 text-[#59745D]" />
                    )}
                  </Card>
                )))}
                {count === 0 && (
                  <p className="text-sm text-[#9A9F9D] italic col-span-full">Nothing planted yet for these years.</p>
                )}
              </div>
            </section>
          );
        })}
      </div>
    </Container>
  );
}
