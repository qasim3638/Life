import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Container, Card, Eyebrow, PageHeader } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Calendar } from "../components/ui/calendar";
import { Plus, Trash2, Cake, Heart, Target, Bell, Star } from "lucide-react";
import { toast } from "sonner";

const TYPES = [
  { key: "birthday", label: "Birthday", icon: Cake },
  { key: "anniversary", label: "Anniversary", icon: Heart },
  { key: "goal", label: "Goal deadline", icon: Target },
  { key: "reminder", label: "Reminder", icon: Bell },
  { key: "event", label: "Special event", icon: Star },
];

export default function Events() {
  const [events, setEvents] = useState([]);
  const [open, setOpen] = useState(false);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [form, setForm] = useState({ title: "", date: new Date().toISOString().slice(0, 10), type: "event", recurring: false, notes: "" });

  const load = async () => {
    const { data } = await api.get("/events");
    setEvents(data);
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.title.trim()) return toast.error("Give it a name");
    await api.post("/events", form);
    toast.success("Added to your calendar");
    setOpen(false);
    setForm({ title: "", date: new Date().toISOString().slice(0, 10), type: "event", recurring: false, notes: "" });
    load();
  };

  const remove = async (id) => { await api.delete(`/events/${id}`); load(); };

  const today = new Date().toISOString().slice(0, 10);
  const upcoming = events.filter(e => e.date >= today);
  const past = events.filter(e => e.date < today);

  const dateStr = selectedDate?.toISOString().slice(0, 10);
  const dayEvents = events.filter(e => e.date === dateStr);

  const eventDays = events.map(e => new Date(e.date));

  return (
    <Container>
      <PageHeader
        eyebrow="The dates that matter"
        title="Mark the moments. Remember the people."
        subtitle="Birthdays, anniversaries, quiet reminders to call someone. A life is made of these."
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Calendar */}
        <Card className="lg:col-span-1" data-testid="events-calendar">
          <Eyebrow>Calendar</Eyebrow>
          <div className="mt-2 flex justify-center">
            <Calendar
              mode="single"
              selected={selectedDate}
              onSelect={setSelectedDate}
              modifiers={{ hasEvent: eventDays }}
              modifiersStyles={{
                hasEvent: { backgroundColor: "#C27A62", color: "white", borderRadius: "9999px" }
              }}
              className="rounded-2xl"
            />
          </div>
          <div className="mt-5">
            <Eyebrow>On this day</Eyebrow>
            {dayEvents.length === 0 ? (
              <p className="text-sm text-[#9A9F9D] italic mt-2">Quiet day.</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {dayEvents.map(e => (
                  <li key={e.id} className="text-sm text-[#2D312E] bg-[#F4F1EA] px-3 py-2 rounded-xl">
                    <span className="text-[10px] uppercase tracking-wider text-[#C27A62] block">{e.type}</span>
                    {e.title}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>

        {/* Upcoming list + Add */}
        <div className="lg:col-span-2 space-y-8">
          <div className="flex items-center justify-between">
            <div>
              <Eyebrow>Coming up</Eyebrow>
              <h2 className="font-serif text-3xl text-[#2D312E]">The near horizon</h2>
            </div>
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button className="rounded-full bg-[#59745D] hover:bg-[#4A604D]" data-testid="add-event-btn">
                  <Plus size={16} className="mr-1"/> Add date
                </Button>
              </DialogTrigger>
              <DialogContent className="rounded-3xl">
                <DialogHeader><DialogTitle className="font-serif text-2xl">Mark a meaningful day</DialogTitle></DialogHeader>
                <div className="space-y-3 mt-2">
                  <Input placeholder="What is it?" value={form.title}
                    onChange={(e) => setForm({ ...form, title: e.target.value })}
                    data-testid="event-title-input"
                  />
                  <Input type="date" value={form.date}
                    onChange={(e) => setForm({ ...form, date: e.target.value })}
                    data-testid="event-date-input"
                  />
                  <Select value={form.type} onValueChange={(v) => setForm({ ...form, type: v })}>
                    <SelectTrigger data-testid="event-type-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {TYPES.map(t => <SelectItem key={t.key} value={t.key}>{t.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <label className="flex items-center gap-2 text-sm text-[#6B7270]">
                    <input type="checkbox" checked={form.recurring}
                      onChange={(e) => setForm({ ...form, recurring: e.target.checked })}
                      data-testid="event-recurring"
                    />
                    Recurs yearly
                  </label>
                  <Textarea placeholder="Notes, what to do, what to remember…"
                    value={form.notes}
                    onChange={(e) => setForm({ ...form, notes: e.target.value })}
                    data-testid="event-notes-input"
                  />
                  <Button onClick={save} className="w-full rounded-full bg-[#59745D]" data-testid="save-event-btn">Save</Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>

          <div className="space-y-3" data-testid="upcoming-list">
            {upcoming.length === 0 && (
              <p className="text-[#6B7270] italic">Nothing yet. Mark a birthday or a goal deadline.</p>
            )}
            {upcoming.map(e => {
              const T = TYPES.find(t => t.key === e.type) || TYPES[4];
              return (
                <div key={e.id} className="flex items-center gap-4 bg-white border border-sand rounded-2xl px-5 py-4" data-testid={`event-${e.id}`}>
                  <div className="w-10 h-10 rounded-full bg-[#F4F1EA] flex items-center justify-center shrink-0">
                    <T.icon size={16} strokeWidth={1.5} className="text-[#C27A62]" />
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-[#2D312E]">{e.title}</p>
                    {e.notes && <p className="text-sm text-[#6B7270] mt-0.5">{e.notes}</p>}
                  </div>
                  <p className="text-sm text-[#6B7270] whitespace-nowrap">{e.date}{e.recurring && " ·↻"}</p>
                  <button onClick={() => remove(e.id)} className="text-[#9A9F9D] hover:text-[#B85C50]">
                    <Trash2 size={15} strokeWidth={1.5}/>
                  </button>
                </div>
              );
            })}
          </div>

          {past.length > 0 && (
            <div>
              <Eyebrow>Passed</Eyebrow>
              <div className="space-y-2 mt-2 opacity-60">
                {past.slice(0, 5).map(e => (
                  <div key={e.id} className="flex justify-between text-sm text-[#6B7270] px-5 py-2">
                    <span>{e.title}</span><span>{e.date}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </Container>
  );
}
