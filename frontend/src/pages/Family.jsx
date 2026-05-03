import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Container, Card, Eyebrow, PageHeader } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Plus, Trash2, Cake, MapPin, Sparkles, BookHeart, Plane, Users } from "lucide-react";
import { toast } from "sonner";

const RELATIONS = ["spouse", "daughter", "son", "mother", "father", "sister", "brother", "child", "friend", "other"];

export default function Family() {
  const [tab, setTab] = useState("members");
  const [view, setView] = useState("cards"); // cards | timeline
  const [members, setMembers] = useState([]);
  const [memories, setMemories] = useState([]);
  const [holidays, setHolidays] = useState([]);

  const load = async () => {
    const [m, mm, h] = await Promise.all([
      api.get("/family/members"), api.get("/family/memories"), api.get("/family/holidays"),
    ]);
    setMembers(m.data); setMemories(mm.data); setHolidays(h.data);
  };
  useEffect(() => { load(); }, []);

  return (
    <Container>
      <PageHeader
        eyebrow="The people"
        title="Family is the long story you write together."
        subtitle="The faces. The holidays. The small ordinary days that turn into memory."
        image="https://images.unsplash.com/photo-1776926635448-1bd49c2ae248"
      />

      <div className="flex flex-wrap items-center gap-2 mb-8">
        {[
          { k: "members", label: "People", icon: Users },
          { k: "memories", label: "Memories", icon: BookHeart },
          { k: "holidays", label: "Holidays", icon: Plane },
        ].map(({ k, label, icon: Icon }) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`flex items-center gap-2 px-5 py-2 rounded-full text-sm transition-colors ${
              tab === k ? "bg-[#59745D] text-white" : "bg-[#F4F1EA] text-[#6B7270] hover:bg-sand"
            }`}
            data-testid={`tab-${k}`}
          >
            <Icon size={14} strokeWidth={1.5}/> {label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2 bg-[#F4F1EA] rounded-full p-1">
          {["cards", "timeline"].map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-4 py-1 rounded-full text-xs uppercase tracking-wider transition-colors ${
                view === v ? "bg-white text-[#2D312E] shadow-sm" : "text-[#6B7270] hover:text-[#2D312E]"
              }`}
              data-testid={`view-${v}`}
            >{v}</button>
          ))}
        </div>
      </div>

      {view === "timeline" ? (
        <Timeline members={members} memories={memories} holidays={holidays}/>
      ) : (
        <>
          {tab === "members" && <Members members={members} reload={load}/>}
          {tab === "memories" && <Memories memories={memories} members={members} reload={load}/>}
          {tab === "holidays" && <Holidays holidays={holidays} members={members} reload={load}/>}
        </>
      )}
    </Container>
  );
}

/* ---------- TIMELINE ---------- */
function Timeline({ members, memories, holidays }) {
  // Build flat events list, sort by date, group by year
  const events = [];
  const today = new Date().toISOString().slice(0, 10);
  members.filter(m => m.birthday).forEach(m => {
    events.push({ kind: "birthday", date: m.birthday, label: `${m.name}'s birthday`, sublabel: m.relation, photo: m.photo_url, future: m.birthday >= today });
  });
  memories.forEach(m => {
    events.push({ kind: "memory", date: m.date, label: m.title, sublabel: m.location, photo: m.photo_url, future: false });
  });
  holidays.forEach(h => {
    events.push({ kind: "holiday", date: h.start_date, label: h.destination, sublabel: `${h.start_date} → ${h.end_date}`, photo: (h.photo_urls || [])[0] || "", future: h.start_date >= today });
  });
  events.sort((a, b) => a.date.localeCompare(b.date));

  // Group by year
  const groups = events.reduce((acc, e) => {
    const y = (e.date || "").slice(0, 4) || "—";
    (acc[y] = acc[y] || []).push(e);
    return acc;
  }, {});
  const years = Object.keys(groups).sort();

  if (events.length === 0) {
    return (
      <Card className="text-center py-16" data-testid="timeline-empty">
        <p className="font-serif text-2xl text-[#2D312E]">Your timeline is waiting.</p>
        <p className="text-[#6B7270] mt-2">Add a person, a memory, or a holiday and watch the chronicle unfold.</p>
      </Card>
    );
  }

  const colors = {
    birthday: "#C27A62",
    memory: "#59745D",
    holiday: "#A3897C",
  };

  return (
    <div className="overflow-x-auto pb-4 -mx-2 px-2" data-testid="timeline-view">
      <div className="relative min-w-[900px]">
        {/* horizontal axis */}
        <div className="absolute left-0 right-0 top-[88px] h-px bg-sand"/>
        <div className="flex gap-12">
          {years.map(y => (
            <section key={y} className="shrink-0" data-testid={`timeline-year-${y}`}>
              <p className="font-serif text-3xl text-[#2D312E] mb-4 pl-1">{y}</p>
              <div className="flex gap-4">
                {groups[y].map((e, i) => (
                  <article
                    key={i}
                    className={`w-56 shrink-0 relative ${e.future ? "" : "opacity-95"}`}
                    data-testid={`timeline-item-${e.kind}`}
                  >
                    {/* dot on axis */}
                    <div className="flex justify-start pl-3">
                      <div
                        className="w-4 h-4 rounded-full ring-4 ring-[#FDFBF7] z-10 relative"
                        style={{ backgroundColor: colors[e.kind] }}
                      />
                    </div>
                    <div className="mt-3 bg-white rounded-2xl border border-sand p-3 hover:-translate-y-1 transition-transform">
                      {e.photo ? (
                        <img src={e.photo} alt="" className="w-full h-28 object-cover rounded-xl mb-2"/>
                      ) : (
                        <div className="w-full h-28 rounded-xl mb-2 flex items-center justify-center"
                          style={{ background: `linear-gradient(135deg, ${colors[e.kind]}33, #F4F1EA)` }}>
                          <span className="font-serif text-3xl" style={{ color: colors[e.kind] }}>
                            {e.kind === "birthday" ? "♡" : e.kind === "holiday" ? "✦" : "·"}
                          </span>
                        </div>
                      )}
                      <p className="text-[10px] uppercase tracking-widest" style={{ color: colors[e.kind] }}>
                        {e.kind} · {e.date}
                      </p>
                      <p className="font-serif text-base text-[#2D312E] leading-tight mt-0.5">{e.label}</p>
                      {e.sublabel && <p className="text-xs text-[#6B7270] mt-1">{e.sublabel}</p>}
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
        <p className="text-xs text-[#9A9F9D] italic mt-4 pl-1">Scroll horizontally to walk through your years →</p>
      </div>
    </div>
  );
}

/* ---------- MEMBERS ---------- */
function Members({ members, reload }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", relation: "spouse", birthday: "", photo_url: "", notes: "" });

  const save = async () => {
    if (!form.name.trim()) return toast.error("Name required");
    await api.post("/family/members", form);
    setOpen(false);
    setForm({ name: "", relation: "spouse", birthday: "", photo_url: "", notes: "" });
    reload();
    toast.success("Added");
  };

  const remove = async (id) => { await api.delete(`/family/members/${id}`); reload(); };

  return (
    <>
      <div className="flex justify-end mb-4">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="rounded-full bg-[#59745D]" data-testid="add-member-btn"><Plus size={14} className="mr-1"/> Add person</Button>
          </DialogTrigger>
          <DialogContent className="rounded-3xl">
            <DialogHeader><DialogTitle className="font-serif text-2xl">Add a family member</DialogTitle></DialogHeader>
            <div className="space-y-3 mt-2">
              <Input placeholder="Name" value={form.name} onChange={(e) => setForm({...form, name: e.target.value})} data-testid="member-name-input"/>
              <Select value={form.relation} onValueChange={(v) => setForm({...form, relation: v})}>
                <SelectTrigger data-testid="member-relation-select"><SelectValue/></SelectTrigger>
                <SelectContent>{RELATIONS.map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
              </Select>
              <Input type="date" value={form.birthday} onChange={(e) => setForm({...form, birthday: e.target.value})} data-testid="member-birthday-input"/>
              <Input placeholder="Photo URL (optional)" value={form.photo_url} onChange={(e) => setForm({...form, photo_url: e.target.value})}/>
              <Textarea placeholder="Notes — what makes them, them" value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})}/>
              <Button onClick={save} className="w-full rounded-full bg-[#59745D]" data-testid="save-member-btn">Save</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {members.length === 0 && (
          <Card className="sm:col-span-2 lg:col-span-3 text-center py-14">
            <p className="font-serif text-2xl text-[#2D312E]">Start with the names you carry.</p>
            <p className="text-[#6B7270] mt-2">Add the people who matter most.</p>
          </Card>
        )}
        {members.map(m => (
          <Card key={m.id} className="flex gap-4 items-start" data-testid={`member-${m.id}`}>
            <div className="w-16 h-16 rounded-full bg-[#F4F1EA] flex items-center justify-center overflow-hidden shrink-0">
              {m.photo_url ? (
                <img src={m.photo_url} alt={m.name} className="w-full h-full object-cover"/>
              ) : (
                <span className="font-serif text-2xl text-[#A3897C]">{m.name?.[0]?.toUpperCase()}</span>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[10px] uppercase tracking-widest text-[#C27A62]">{m.relation}</p>
              <h3 className="font-serif text-xl text-[#2D312E] mt-0.5 truncate">{m.name}</h3>
              {m.birthday && (
                <p className="text-xs text-[#6B7270] mt-1 flex items-center gap-1">
                  <Cake size={12} strokeWidth={1.5}/> {m.birthday}
                </p>
              )}
              {m.notes && <p className="text-sm text-[#6B7270] mt-2 leading-relaxed">{m.notes}</p>}
            </div>
            <button onClick={() => remove(m.id)} className="text-[#9A9F9D] hover:text-[#B85C50]" data-testid={`del-member-${m.id}`}>
              <Trash2 size={14} strokeWidth={1.5}/>
            </button>
          </Card>
        ))}
      </div>
    </>
  );
}

/* ---------- MEMORIES ---------- */
function Memories({ memories, members, reload }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ title: "", date: new Date().toISOString().slice(0,10), location: "", story: "", photo_url: "", member_ids: [] });
  const [editingId, setEditingId] = useState(null);
  const [aiOpen, setAiOpen] = useState(false);
  const [aiText, setAiText] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [active, setActive] = useState(null);

  const openCreate = () => {
    setEditingId(null);
    setForm({ title: "", date: new Date().toISOString().slice(0,10), location: "", story: "", photo_url: "", member_ids: [] });
    setOpen(true);
  };

  const openEdit = (mem) => {
    setEditingId(mem.id);
    setForm({
      title: mem.title || "",
      date: mem.date || new Date().toISOString().slice(0,10),
      location: mem.location || "",
      story: mem.story || "",
      photo_url: mem.photo_url || "",
      member_ids: mem.member_ids || [],
    });
    setActive(null);
    setOpen(true);
  };

  const save = async () => {
    if (!form.title.trim()) return toast.error("Give it a title");
    if (editingId) {
      await api.put(`/family/memories/${editingId}`, form);
      toast.success("Updated");
    } else {
      await api.post("/family/memories", form);
      toast.success("Saved");
    }
    setOpen(false);
    setEditingId(null);
    setForm({ title: "", date: new Date().toISOString().slice(0,10), location: "", story: "", photo_url: "", member_ids: [] });
    reload();
  };

  const remove = async (id) => { await api.delete(`/family/memories/${id}`); reload(); };

  const weave = async (mem) => {
    setAiOpen(true); setAiText(""); setAiLoading(true);
    try {
      const ctx = `Title: ${mem.title}. Date: ${mem.date}. Location: ${mem.location || "—"}. Story: ${mem.story || "—"}`;
      const { data } = await api.post("/ai/memory-weave", { prompt: ctx });
      setAiText(data.text);
    } catch { toast.error("AI is resting"); }
    finally { setAiLoading(false); }
  };

  const toggleMember = (id) => {
    setForm(f => ({ ...f, member_ids: f.member_ids.includes(id) ? f.member_ids.filter(x => x !== id) : [...f.member_ids, id] }));
  };

  return (
    <>
      <div className="flex justify-end mb-4">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button onClick={openCreate} className="rounded-full bg-[#59745D]" data-testid="add-memory-btn"><Plus size={14} className="mr-1"/> Capture a memory</Button>
          </DialogTrigger>
          <DialogContent className="rounded-3xl max-w-xl max-h-[90vh] overflow-y-auto">
            <DialogHeader><DialogTitle className="font-serif text-2xl">{editingId ? "Edit memory" : "A moment worth keeping"}</DialogTitle></DialogHeader>
            <div className="space-y-3 mt-2">
              <Input placeholder="Title (e.g., First snow with Maya)" value={form.title} onChange={(e) => setForm({...form, title: e.target.value})} data-testid="memory-title-input"/>
              <div className="grid grid-cols-2 gap-3">
                <Input type="date" value={form.date} onChange={(e) => setForm({...form, date: e.target.value})}/>
                <Input placeholder="Location" value={form.location} onChange={(e) => setForm({...form, location: e.target.value})}/>
              </div>
              <Input placeholder="Photo URL (optional)" value={form.photo_url} onChange={(e) => setForm({...form, photo_url: e.target.value})} data-testid="memory-photo-input"/>
              <Textarea placeholder="Tell the story — sensory, specific, true" rows={4} value={form.story} onChange={(e) => setForm({...form, story: e.target.value})} data-testid="memory-story-input"/>
              {members.length > 0 && (
                <div>
                  <p className="text-xs uppercase tracking-widest text-[#9A9F9D] mb-2">Who was there</p>
                  <div className="flex flex-wrap gap-2">
                    {members.map(m => (
                      <button key={m.id} type="button" onClick={() => toggleMember(m.id)}
                        className={`px-3 py-1 rounded-full text-xs ${form.member_ids.includes(m.id) ? "bg-[#59745D] text-white" : "bg-[#F4F1EA] text-[#6B7270]"}`}
                      >{m.name}</button>
                    ))}
                  </div>
                </div>
              )}
              <Button onClick={save} className="w-full rounded-full bg-[#59745D]" data-testid="save-memory-btn">{editingId ? "Update" : "Keep this"}</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {memories.length === 0 && (
          <Card className="sm:col-span-2 lg:col-span-3 text-center py-14">
            <p className="font-serif text-2xl text-[#2D312E]">No memories saved yet.</p>
            <p className="text-[#6B7270] mt-2">A photo. A line. A date. That's enough.</p>
          </Card>
        )}
        {memories.map(m => (
          <Card key={m.id} className="p-0 overflow-hidden cursor-pointer group" onClick={() => setActive(m)} data-testid={`memory-${m.id}`}>
            <div className="aspect-[4/3] bg-[#F4F1EA] relative overflow-hidden">
              {m.photo_url ? (
                <img src={m.photo_url} alt={m.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform"/>
              ) : (
                <div className="absolute inset-0 flex items-center justify-center">
                  <BookHeart size={36} strokeWidth={1} className="text-[#A3897C]/40"/>
                </div>
              )}
              <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent"/>
              <div className="absolute bottom-3 left-4 right-4 text-white">
                <p className="text-[10px] uppercase tracking-widest opacity-80">{m.date}</p>
                <h3 className="font-serif text-lg leading-tight">{m.title}</h3>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Detail dialog */}
      <Dialog open={!!active} onOpenChange={() => setActive(null)}>
        <DialogContent className="rounded-3xl max-w-2xl max-h-[90vh] overflow-y-auto p-0">
          {active && (
            <>
              {active.photo_url && <img src={active.photo_url} alt={active.title} className="w-full h-64 object-cover rounded-t-3xl"/>}
              <div className="p-7">
                <p className="text-xs uppercase tracking-[0.3em] text-[#C27A62]">{active.date}{active.location && ` · ${active.location}`}</p>
                <h2 className="font-serif text-3xl text-[#2D312E] mt-1">{active.title}</h2>
                {active.member_ids?.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {active.member_ids.map(id => {
                      const mem = members.find(x => x.id === id);
                      return mem && <span key={id} className="px-3 py-1 rounded-full text-xs bg-[#F4F1EA]">{mem.name}</span>;
                    })}
                  </div>
                )}
                {active.story && <p className="mt-4 text-[#2D312E] leading-relaxed whitespace-pre-wrap">{active.story}</p>}
                <div className="flex gap-2 mt-6">
                  <Button onClick={() => weave(active)} variant="outline" className="rounded-full border-[#C27A62] text-[#C27A62] hover:bg-[#C27A62] hover:text-white" data-testid="weave-memory-btn">
                    <Sparkles size={14} className="mr-1" strokeWidth={1.5}/> Weave a reflection
                  </Button>
                  <Button onClick={() => openEdit(active)} variant="ghost" className="rounded-full text-[#59745D]" data-testid="edit-memory-btn">
                    Edit
                  </Button>
                  <Button onClick={() => { remove(active.id); setActive(null); }} variant="ghost" className="rounded-full text-[#9A9F9D] hover:text-[#B85C50] ml-auto">
                    <Trash2 size={14} strokeWidth={1.5}/>
                  </Button>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={aiOpen} onOpenChange={setAiOpen}>
        <DialogContent className="rounded-3xl">
          <DialogHeader><DialogTitle className="font-serif text-2xl">A reflection</DialogTitle></DialogHeader>
          {aiLoading ? <p className="text-[#6B7270]">Weaving…</p> :
            <p className="font-serif text-lg text-[#2D312E] leading-relaxed whitespace-pre-wrap">{aiText}</p>
          }
        </DialogContent>
      </Dialog>
    </>
  );
}

/* ---------- HOLIDAYS ---------- */
function Holidays({ holidays, members, reload }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ destination: "", start_date: "", end_date: "", status: "planned", budget: "", notes: "", todos: [], photo_urls: [], member_ids: [] });
  const [aiOpen, setAiOpen] = useState(false);
  const [aiText, setAiText] = useState("");
  const [aiLoading, setAiLoading] = useState(false);

  const save = async () => {
    if (!form.destination.trim() || !form.start_date) return toast.error("Destination and dates required");
    await api.post("/family/holidays", form);
    setOpen(false);
    setForm({ destination: "", start_date: "", end_date: "", status: "planned", budget: "", notes: "", todos: [], photo_urls: [], member_ids: [] });
    reload();
    toast.success("Saved");
  };

  const remove = async (id) => { await api.delete(`/family/holidays/${id}`); reload(); };

  const plan = async (h) => {
    setAiOpen(true); setAiText(""); setAiLoading(true);
    try {
      const ctx = `Destination: ${h.destination}. Dates: ${h.start_date} to ${h.end_date}. Notes: ${h.notes || "—"}`;
      const { data } = await api.post("/ai/holiday-planner", { prompt: ctx });
      setAiText(data.text);
    } catch { toast.error("AI is resting"); }
    finally { setAiLoading(false); }
  };

  const updateStatus = async (h, status) => {
    await api.put(`/family/holidays/${h.id}`, { ...h, status });
    reload();
  };

  const today = new Date().toISOString().slice(0,10);
  const upcoming = holidays.filter(h => h.start_date >= today);
  const past = holidays.filter(h => h.start_date < today);

  return (
    <>
      <div className="flex justify-end mb-4">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="rounded-full bg-[#59745D]" data-testid="add-holiday-btn"><Plus size={14} className="mr-1"/> Plan a trip</Button>
          </DialogTrigger>
          <DialogContent className="rounded-3xl max-w-xl">
            <DialogHeader><DialogTitle className="font-serif text-2xl">A trip worth taking</DialogTitle></DialogHeader>
            <div className="space-y-3 mt-2">
              <Input placeholder="Destination" value={form.destination} onChange={(e) => setForm({...form, destination: e.target.value})} data-testid="holiday-dest-input"/>
              <div className="grid grid-cols-2 gap-3">
                <Input type="date" value={form.start_date} onChange={(e) => setForm({...form, start_date: e.target.value})}/>
                <Input type="date" value={form.end_date} onChange={(e) => setForm({...form, end_date: e.target.value})}/>
              </div>
              <Input placeholder="Budget (free text)" value={form.budget} onChange={(e) => setForm({...form, budget: e.target.value})}/>
              <Textarea placeholder="Notes — anchors, must-sees, vibe" rows={3} value={form.notes} onChange={(e) => setForm({...form, notes: e.target.value})}/>
              <Button onClick={save} className="w-full rounded-full bg-[#59745D]" data-testid="save-holiday-btn">Save</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {[{ list: upcoming, title: "Coming up" }, { list: past, title: "Already lived" }].map(({ list, title }) => list.length > 0 && (
        <section key={title} className="mb-10">
          <Eyebrow>{title}</Eyebrow>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-3">
            {list.map(h => (
              <Card key={h.id} data-testid={`holiday-${h.id}`}>
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-[10px] uppercase tracking-widest text-[#C27A62]">{h.status}</p>
                    <h3 className="font-serif text-2xl text-[#2D312E] mt-1 flex items-center gap-2">
                      <MapPin size={15} strokeWidth={1.5}/> {h.destination}
                    </h3>
                    <p className="text-sm text-[#6B7270] mt-1">{h.start_date} → {h.end_date}</p>
                  </div>
                  <button onClick={() => remove(h.id)} className="text-[#9A9F9D] hover:text-[#B85C50]"><Trash2 size={14} strokeWidth={1.5}/></button>
                </div>
                {h.budget && <p className="text-sm text-[#6B7270] mt-2">Budget: {h.budget}</p>}
                {h.notes && <p className="text-sm text-[#2D312E] mt-2 leading-relaxed">{h.notes}</p>}
                <div className="flex flex-wrap gap-2 mt-4">
                  {["planned","booked","completed"].map(s => (
                    <button key={s} onClick={() => updateStatus(h, s)}
                      className={`px-3 py-1 rounded-full text-xs ${h.status === s ? "bg-[#59745D] text-white" : "bg-[#F4F1EA] text-[#6B7270]"}`}
                    >{s}</button>
                  ))}
                  <Button size="sm" variant="ghost" onClick={() => plan(h)} className="rounded-full text-[#C27A62] ml-auto" data-testid={`plan-holiday-${h.id}`}>
                    <Sparkles size={13} strokeWidth={1.5} className="mr-1"/> AI plan
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </section>
      ))}

      {holidays.length === 0 && (
        <Card className="text-center py-14">
          <p className="font-serif text-2xl text-[#2D312E]">No trips yet.</p>
          <p className="text-[#6B7270] mt-2">The next one might be the best one. Plan it.</p>
        </Card>
      )}

      <Dialog open={aiOpen} onOpenChange={setAiOpen}>
        <DialogContent className="rounded-3xl max-w-xl">
          <DialogHeader><DialogTitle className="font-serif text-2xl">Itinerary draft</DialogTitle></DialogHeader>
          {aiLoading ? <p className="text-[#6B7270]">Mapping…</p> :
            <p className="text-[#2D312E] leading-relaxed whitespace-pre-wrap">{aiText}</p>
          }
        </DialogContent>
      </Dialog>
    </>
  );
}
