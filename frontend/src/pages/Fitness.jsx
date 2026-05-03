import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Container, Card, Eyebrow, PageHeader } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Plus, Trash2, Sparkles, Play, X } from "lucide-react";
import { toast } from "sonner";

const CATEGORIES = ["Strength", "Cardio", "Mobility", "Yoga", "HIIT", "Walk"];

export default function Fitness() {
  const [workouts, setWorkouts] = useState([]);
  const [logs, setLogs] = useState([]);
  const [openBuilder, setOpenBuilder] = useState(false);
  const [openLog, setOpenLog] = useState(null);
  const [aiOpen, setAiOpen] = useState(false);
  const [aiText, setAiText] = useState("");
  const [aiFocus, setAiFocus] = useState("longevity strength");
  const [aiLoading, setAiLoading] = useState(false);

  const [builder, setBuilder] = useState({
    name: "", category: "Strength", notes: "",
    exercises: [{ name: "", sets: 3, reps: 10, rest: 60 }],
  });

  const load = async () => {
    const [w, l] = await Promise.all([api.get("/workouts"), api.get("/workout-logs")]);
    setWorkouts(w.data); setLogs(l.data);
  };
  useEffect(() => { load(); }, []);

  const addExercise = () => setBuilder({ ...builder, exercises: [...builder.exercises, { name: "", sets: 3, reps: 10, rest: 60 }] });
  const setEx = (i, k, v) => {
    const ex = [...builder.exercises];
    ex[i] = { ...ex[i], [k]: v };
    setBuilder({ ...builder, exercises: ex });
  };
  const removeEx = (i) => setBuilder({ ...builder, exercises: builder.exercises.filter((_, idx) => idx !== i) });

  const saveWorkout = async () => {
    if (!builder.name.trim()) return toast.error("Give your workout a name");
    await api.post("/workouts", builder);
    toast.success("Workout saved");
    setOpenBuilder(false);
    setBuilder({ name: "", category: "Strength", notes: "", exercises: [{ name: "", sets: 3, reps: 10, rest: 60 }] });
    load();
  };

  const logWorkout = async (w, duration, notes) => {
    await api.post("/workout-logs", {
      workout_id: w.id, workout_name: w.name,
      date: new Date().toISOString().slice(0, 10),
      duration_min: parseInt(duration || 30), notes: notes || "",
    });
    toast.success("Logged. Nice work.");
    setOpenLog(null);
    load();
  };

  const removeWorkout = async (id) => {
    await api.delete(`/workouts/${id}`);
    load();
  };

  const askAI = async () => {
    setAiLoading(true);
    try {
      const { data } = await api.post("/ai/workout-suggestion", { prompt: aiFocus });
      setAiText(data.text);
    } catch { toast.error("AI is resting"); }
    finally { setAiLoading(false); }
  };

  return (
    <Container>
      <PageHeader
        eyebrow="Joyful movement"
        title="Move like you plan to do this for 40 more years."
        subtitle="Not punishment. Not performance. Practice."
        image="https://images.unsplash.com/photo-1776926635448-1bd49c2ae248"
      />

      <div className="flex flex-wrap items-center gap-3 mb-8">
        <Dialog open={openBuilder} onOpenChange={setOpenBuilder}>
          <DialogTrigger asChild>
            <Button className="rounded-full bg-[#59745D] hover:bg-[#4A604D]" data-testid="add-workout-btn">
              <Plus size={16} className="mr-1" /> Build a workout
            </Button>
          </DialogTrigger>
          <DialogContent className="rounded-3xl max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader><DialogTitle className="font-serif text-2xl">Design your movement</DialogTitle></DialogHeader>
            <div className="space-y-4 mt-2">
              <Input placeholder="Workout name" value={builder.name}
                onChange={(e) => setBuilder({ ...builder, name: e.target.value })}
                data-testid="workout-name-input"
              />
              <Select value={builder.category} onValueChange={(v) => setBuilder({ ...builder, category: v })}>
                <SelectTrigger data-testid="workout-category-select"><SelectValue /></SelectTrigger>
                <SelectContent>{CATEGORIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
              </Select>
              <div>
                <Eyebrow>Exercises</Eyebrow>
                <div className="space-y-3 mt-2">
                  {builder.exercises.map((ex, i) => (
                    <div key={i} className="flex gap-2 items-center">
                      <Input placeholder="Exercise" value={ex.name} className="flex-1"
                        onChange={(e) => setEx(i, "name", e.target.value)}
                        data-testid={`ex-name-${i}`}
                      />
                      <Input type="number" placeholder="Sets" className="w-16" value={ex.sets}
                        onChange={(e) => setEx(i, "sets", parseInt(e.target.value))}
                        data-testid={`ex-sets-${i}`}
                      />
                      <Input type="number" placeholder="Reps" className="w-16" value={ex.reps}
                        onChange={(e) => setEx(i, "reps", parseInt(e.target.value))}
                        data-testid={`ex-reps-${i}`}
                      />
                      <Input type="number" placeholder="Rest(s)" className="w-20" value={ex.rest}
                        onChange={(e) => setEx(i, "rest", parseInt(e.target.value))}
                      />
                      <button onClick={() => removeEx(i)} className="text-[#9A9F9D] hover:text-[#B85C50]">
                        <X size={16} />
                      </button>
                    </div>
                  ))}
                </div>
                <Button variant="ghost" onClick={addExercise} className="mt-2 rounded-full text-[#59745D]" data-testid="add-exercise-btn">
                  <Plus size={14} className="mr-1" /> Add exercise
                </Button>
              </div>
              <Textarea placeholder="Notes (intention, form cues…)" value={builder.notes}
                onChange={(e) => setBuilder({ ...builder, notes: e.target.value })}
              />
              <Button onClick={saveWorkout} className="w-full rounded-full bg-[#59745D]" data-testid="save-workout-btn">Save workout</Button>
            </div>
          </DialogContent>
        </Dialog>

        <Dialog open={aiOpen} onOpenChange={setAiOpen}>
          <DialogTrigger asChild>
            <Button variant="outline" className="rounded-full border-[#59745D] text-[#59745D] hover:bg-[#59745D] hover:text-white" data-testid="ai-workout-btn">
              <Sparkles size={15} className="mr-1" strokeWidth={1.5} /> Ask AI coach
            </Button>
          </DialogTrigger>
          <DialogContent className="rounded-3xl">
            <DialogHeader><DialogTitle className="font-serif text-2xl">Design with AI</DialogTitle></DialogHeader>
            <Input placeholder="Focus (e.g., mobility after work)" value={aiFocus} onChange={(e) => setAiFocus(e.target.value)} data-testid="ai-focus-input"/>
            <Button onClick={askAI} disabled={aiLoading} className="rounded-full bg-[#59745D]" data-testid="ai-generate-workout-btn">
              {aiLoading ? "Thinking…" : "Generate"}
            </Button>
            {aiText && (
              <div className="bg-[#F4F1EA] rounded-2xl p-5 whitespace-pre-wrap text-sm leading-relaxed text-[#2D312E]">
                {aiText}
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {workouts.length === 0 && (
          <Card className="md:col-span-3 text-center py-16" data-testid="empty-workouts">
            <p className="font-serif text-2xl text-[#2D312E]">Your first workout awaits.</p>
            <p className="text-[#6B7270] mt-2">Build one, or ask the AI coach for a tailored plan.</p>
          </Card>
        )}
        {workouts.map(w => (
          <Card key={w.id} data-testid={`workout-${w.id}`} className="flex flex-col">
            <Eyebrow>{w.category}</Eyebrow>
            <h3 className="font-serif text-2xl text-[#2D312E]">{w.name}</h3>
            <ul className="mt-3 space-y-1.5 text-sm text-[#6B7270]">
              {w.exercises.slice(0, 4).map((e, i) => (
                <li key={i}>{e.name || "—"} · {e.sets}×{e.reps}</li>
              ))}
              {w.exercises.length > 4 && <li className="text-xs text-[#9A9F9D]">+{w.exercises.length - 4} more</li>}
            </ul>
            <div className="mt-auto pt-4 flex items-center gap-2">
              <Button
                size="sm"
                className="rounded-full bg-[#59745D] hover:bg-[#4A604D]"
                onClick={() => setOpenLog(w)}
                data-testid={`log-workout-${w.id}`}
              >
                <Play size={14} className="mr-1" strokeWidth={1.5} /> Log
              </Button>
              <button onClick={() => removeWorkout(w.id)} className="ml-auto text-[#9A9F9D] hover:text-[#B85C50]">
                <Trash2 size={16} strokeWidth={1.5} />
              </button>
            </div>
          </Card>
        ))}
      </div>

      {/* Log Dialog */}
      <Dialog open={!!openLog} onOpenChange={() => setOpenLog(null)}>
        <DialogContent className="rounded-3xl">
          <DialogHeader><DialogTitle className="font-serif text-2xl">Log: {openLog?.name}</DialogTitle></DialogHeader>
          <LogForm onSubmit={(d, n) => logWorkout(openLog, d, n)} />
        </DialogContent>
      </Dialog>

      {logs.length > 0 && (
        <section className="mt-14">
          <Eyebrow>Recent logs</Eyebrow>
          <h2 className="font-serif text-3xl text-[#2D312E] mb-4">The record you're writing</h2>
          <div className="space-y-2">
            {logs.slice(0, 10).map(l => (
              <div key={l.id} className="flex items-center justify-between bg-white rounded-2xl border border-sand px-5 py-3" data-testid={`log-${l.id}`}>
                <div>
                  <p className="font-medium text-[#2D312E]">{l.workout_name}</p>
                  <p className="text-xs text-[#9A9F9D] mt-0.5">{l.date}</p>
                </div>
                <p className="text-sm text-[#6B7270]">{l.duration_min} min</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </Container>
  );
}

function LogForm({ onSubmit }) {
  const [duration, setDuration] = useState(30);
  const [notes, setNotes] = useState("");
  return (
    <div className="space-y-3 mt-2">
      <Input type="number" value={duration} onChange={(e) => setDuration(e.target.value)} placeholder="Minutes" data-testid="log-duration-input"/>
      <Textarea placeholder="How did it feel?" value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="log-notes-input"/>
      <Button onClick={() => onSubmit(duration, notes)} className="w-full rounded-full bg-[#59745D]" data-testid="submit-log-btn">Log it</Button>
    </div>
  );
}
