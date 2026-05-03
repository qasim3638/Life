import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Container, Card, Eyebrow, PageHeader } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Plus, X, Save, Sun, Moon, Pill, Briefcase, Home as HomeIcon, Droplet, Dumbbell, ChefHat, Clock } from "lucide-react";
import { toast } from "sonner";

const MEAL_KEYS = [
  { key: "breakfast", label: "Breakfast", icon: Sun },
  { key: "lunch", label: "Lunch", icon: ChefHat },
  { key: "dinner", label: "Dinner", icon: Moon },
  { key: "snack", label: "Snack", icon: ChefHat },
];

const empty = {
  priorities: ["", "", ""],
  gym_planned: false,
  gym_workout_id: "",
  gym_workout_name: "",
  meals: {
    breakfast: { text: "", recipe_id: "" },
    lunch: { text: "", recipe_id: "" },
    dinner: { text: "", recipe_id: "" },
    snack: { text: "", recipe_id: "" },
  },
  supplements: [],
  house_chores: [],
  work_chores: [],
  time_blocks: [],
  sleep_target: "23:00",
  wake_target: "06:30",
  hydration_oz: 80,
  notes: "",
};

function buildHourSlots(wake, sleep) {
  // Generate 1-hour slots from wake to sleep (handles wrap)
  const [wh, wm] = (wake || "06:30").split(":").map(Number);
  const [sh, sm] = (sleep || "23:00").split(":").map(Number);
  const startMin = wh * 60 + wm;
  let endMin = sh * 60 + sm;
  if (endMin <= startMin) endMin += 24 * 60;
  const slots = [];
  for (let m = Math.floor(startMin / 60) * 60; m < endMin; m += 60) {
    const h = Math.floor((m % (24 * 60)) / 60);
    slots.push(`${String(h).padStart(2, "0")}:00`);
  }
  return slots;
}

export default function Tomorrow() {
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  const [date, setDate] = useState(tomorrow);
  const [plan, setPlan] = useState(empty);
  const [recipes, setRecipes] = useState([]);
  const [workouts, setWorkouts] = useState([]);
  const [saving, setSaving] = useState(false);

  const load = async (d) => {
    const [p, r, w] = await Promise.all([
      api.get(`/day-plans/${d}`),
      api.get("/recipes"),
      api.get("/workouts"),
    ]);
    setPlan({ ...empty, ...p.data, meals: { ...empty.meals, ...(p.data.meals || {}) } });
    setRecipes(r.data);
    setWorkouts(w.data);
  };

  useEffect(() => { load(date); }, [date]);

  const save = async () => {
    setSaving(true);
    try {
      await api.put(`/day-plans/${date}`, { ...plan, date });
      toast.success("Tomorrow is planned");
    } catch { toast.error("Couldn't save"); }
    finally { setSaving(false); }
  };

  // helpers
  const setMeal = (key, val) => setPlan({ ...plan, meals: { ...plan.meals, [key]: { ...plan.meals[key], ...val } } });
  const setPriority = (i, v) => {
    const p = [...plan.priorities];
    p[i] = v;
    setPlan({ ...plan, priorities: p });
  };

  const addItem = (field) => setPlan({ ...plan, [field]: [...plan[field], { text: "", done: false }] });
  const updItem = (field, i, v) => {
    const arr = [...plan[field]];
    arr[i] = { ...arr[i], ...v };
    setPlan({ ...plan, [field]: arr });
  };
  const removeItem = (field, i) => {
    setPlan({ ...plan, [field]: plan[field].filter((_, idx) => idx !== i) });
  };

  const addSupp = () => setPlan({ ...plan, supplements: [...plan.supplements, { name: "", taken: false }] });
  const updSupp = (i, v) => {
    const arr = [...plan.supplements];
    arr[i] = { ...arr[i], ...v };
    setPlan({ ...plan, supplements: arr });
  };
  const removeSupp = (i) => setPlan({ ...plan, supplements: plan.supplements.filter((_, idx) => idx !== i) });

  const slots = buildHourSlots(plan.wake_target, plan.sleep_target);
  const blockMap = (plan.time_blocks || []).reduce((m, b) => ({ ...m, [b.hour]: b.text }), {});
  const setBlock = (hour, text) => {
    const others = (plan.time_blocks || []).filter(b => b.hour !== hour);
    const blocks = text ? [...others, { hour, text }] : others;
    blocks.sort((a, b) => a.hour.localeCompare(b.hour));
    setPlan({ ...plan, time_blocks: blocks });
  };

  const fmtHour = (hh) => {
    const [h] = hh.split(":").map(Number);
    const ap = h < 12 ? "AM" : "PM";
    const h12 = ((h + 11) % 12) + 1;
    return `${h12} ${ap}`;
  };

  const dateLabel = new Date(date + "T00:00").toLocaleDateString(undefined, {
    weekday: "long", month: "long", day: "numeric",
  });

  return (
    <Container>
      <PageHeader
        eyebrow="Plan tomorrow"
        title={`A gentler ${dateLabel.split(",")[0].toLowerCase()} starts tonight.`}
        subtitle="Decide once. Move easily. Tomorrow you will thank tonight you."
      />

      <div className="flex flex-wrap items-center gap-3 mb-8">
        <Input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="max-w-xs rounded-full"
          data-testid="plan-date-input"
        />
        <Button
          onClick={save}
          disabled={saving}
          className="rounded-full bg-[#59745D] hover:bg-[#4A604D] ml-auto"
          data-testid="save-plan-btn"
        >
          <Save size={15} className="mr-1" strokeWidth={1.5}/>
          {saving ? "Saving…" : "Save plan"}
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top 3 priorities */}
        <Card className="lg:col-span-3 bg-[#F4F1EA] border-0" data-testid="priorities-card">
          <Eyebrow>Three things that matter</Eyebrow>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
            {plan.priorities.map((p, i) => (
              <div key={i} className="relative">
                <div className="absolute left-4 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-[#C27A62] text-white text-xs font-medium flex items-center justify-center">
                  {i + 1}
                </div>
                <Input
                  value={p}
                  onChange={(e) => setPriority(i, e.target.value)}
                  placeholder={i === 0 ? "Most important" : i === 1 ? "Important" : "If time"}
                  className="rounded-full bg-white pl-12"
                  data-testid={`priority-${i}`}
                />
              </div>
            ))}
          </div>
        </Card>

        {/* Gym */}
        <Card data-testid="gym-card">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Dumbbell size={18} strokeWidth={1.5} className="text-[#59745D]"/>
              <Eyebrow>Movement</Eyebrow>
            </div>
            <button
              onClick={() => setPlan({ ...plan, gym_planned: !plan.gym_planned })}
              className={`px-4 py-1.5 rounded-full text-xs uppercase tracking-wider transition-colors ${
                plan.gym_planned ? "bg-[#59745D] text-white" : "bg-[#F4F1EA] text-[#6B7270]"
              }`}
              data-testid="gym-toggle"
            >
              {plan.gym_planned ? "Yes" : "Rest day"}
            </button>
          </div>
          {plan.gym_planned && (
            <div className="mt-4">
              <Select value={plan.gym_workout_id || "_none"} onValueChange={(v) => {
                if (v === "_none") return setPlan({ ...plan, gym_workout_id: "", gym_workout_name: "" });
                const w = workouts.find(x => x.id === v);
                setPlan({ ...plan, gym_workout_id: v, gym_workout_name: w?.name || "" });
              }}>
                <SelectTrigger data-testid="gym-workout-select"><SelectValue placeholder="Pick workout"/></SelectTrigger>
                <SelectContent>
                  <SelectItem value="_none">No specific workout</SelectItem>
                  {workouts.map(w => <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>)}
                </SelectContent>
              </Select>
              {plan.gym_workout_name && (
                <p className="text-sm text-[#6B7270] mt-2">Planned: <span className="text-[#2D312E]">{plan.gym_workout_name}</span></p>
              )}
            </div>
          )}
        </Card>

        {/* Sleep */}
        <Card data-testid="sleep-card">
          <div className="flex items-center gap-2">
            <Moon size={18} strokeWidth={1.5} className="text-[#A3897C]"/>
            <Eyebrow>Sleep window</Eyebrow>
          </div>
          <div className="grid grid-cols-2 gap-3 mt-3">
            <div>
              <p className="text-[10px] uppercase tracking-widest text-[#9A9F9D] mb-1">Lights out</p>
              <Input type="time" value={plan.sleep_target}
                onChange={(e) => setPlan({ ...plan, sleep_target: e.target.value })}
                data-testid="sleep-target"
              />
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-widest text-[#9A9F9D] mb-1">Wake</p>
              <Input type="time" value={plan.wake_target}
                onChange={(e) => setPlan({ ...plan, wake_target: e.target.value })}
                data-testid="wake-target"
              />
            </div>
          </div>
        </Card>

        {/* Hydration */}
        <Card data-testid="hydration-card">
          <div className="flex items-center gap-2">
            <Droplet size={18} strokeWidth={1.5} className="text-[#59745D]"/>
            <Eyebrow>Hydration</Eyebrow>
          </div>
          <div className="mt-3">
            <Input type="number" value={plan.hydration_oz}
              onChange={(e) => setPlan({ ...plan, hydration_oz: parseInt(e.target.value) || 0 })}
              data-testid="hydration-input"
            />
            <p className="text-xs text-[#9A9F9D] mt-1">ounces (≈ {Math.round(plan.hydration_oz * 29.5)} ml)</p>
          </div>
        </Card>

        {/* Meals */}
        <Card className="lg:col-span-3" data-testid="meals-card">
          <div className="flex items-center gap-2 mb-4">
            <ChefHat size={18} strokeWidth={1.5} className="text-[#C27A62]"/>
            <Eyebrow>Tomorrow's meals</Eyebrow>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {MEAL_KEYS.map(({ key, label, icon: Icon }) => (
              <div key={key} className="bg-[#F4F1EA] rounded-2xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Icon size={15} strokeWidth={1.5} className="text-[#A3897C]"/>
                  <p className="font-serif text-lg text-[#2D312E]">{label}</p>
                </div>
                <Input
                  value={plan.meals[key]?.text || ""}
                  onChange={(e) => setMeal(key, { text: e.target.value })}
                  placeholder="Free text or pick a recipe…"
                  className="bg-white mb-2 rounded-full"
                  data-testid={`meal-${key}-text`}
                />
                <Select
                  value={plan.meals[key]?.recipe_id || "_none"}
                  onValueChange={(v) => {
                    if (v === "_none") return setMeal(key, { recipe_id: "" });
                    const r = recipes.find(x => x.id === v);
                    setMeal(key, { recipe_id: v, text: plan.meals[key]?.text || r?.title || "" });
                  }}
                >
                  <SelectTrigger className="bg-white" data-testid={`meal-${key}-recipe`}>
                    <SelectValue placeholder="Or pick from recipes"/>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="_none">No recipe linked</SelectItem>
                    {recipes.map(r => <SelectItem key={r.id} value={r.id}>{r.title}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            ))}
          </div>
        </Card>

        {/* Supplements */}
        <Card data-testid="supplements-card">
          <div className="flex items-center gap-2 mb-3">
            <Pill size={18} strokeWidth={1.5} className="text-[#C27A62]"/>
            <Eyebrow>Supplements</Eyebrow>
          </div>
          <div className="space-y-2">
            {plan.supplements.map((s, i) => (
              <div key={i} className="flex items-center gap-2" data-testid={`supp-${i}`}>
                <input type="checkbox" checked={s.taken}
                  onChange={(e) => updSupp(i, { taken: e.target.checked })}
                  className="w-4 h-4 accent-[#59745D]"
                />
                <Input
                  value={s.name}
                  onChange={(e) => updSupp(i, { name: e.target.value })}
                  placeholder="e.g., Vitamin D"
                  className="rounded-full flex-1"
                />
                <button onClick={() => removeSupp(i)} className="text-[#9A9F9D] hover:text-[#B85C50]"><X size={15}/></button>
              </div>
            ))}
          </div>
          <Button variant="ghost" onClick={addSupp} className="rounded-full text-[#59745D] mt-2" data-testid="add-supp-btn">
            <Plus size={14} className="mr-1"/> Add supplement
          </Button>
        </Card>

        {/* House chores */}
        <Card data-testid="house-chores-card">
          <div className="flex items-center gap-2 mb-3">
            <HomeIcon size={18} strokeWidth={1.5} className="text-[#A3897C]"/>
            <Eyebrow>House chores</Eyebrow>
          </div>
          <ChoreList
            items={plan.house_chores}
            field="house_chores"
            onUpdate={updItem}
            onRemove={removeItem}
            placeholder="Laundry, take out trash…"
            testid="house"
          />
          <Button variant="ghost" onClick={() => addItem("house_chores")} className="rounded-full text-[#59745D] mt-2" data-testid="add-house-chore">
            <Plus size={14} className="mr-1"/> Add chore
          </Button>
        </Card>

        {/* Work chores */}
        <Card data-testid="work-chores-card">
          <div className="flex items-center gap-2 mb-3">
            <Briefcase size={18} strokeWidth={1.5} className="text-[#59745D]"/>
            <Eyebrow>Work tasks</Eyebrow>
          </div>
          <ChoreList
            items={plan.work_chores}
            field="work_chores"
            onUpdate={updItem}
            onRemove={removeItem}
            placeholder="Email, deep work block…"
            testid="work"
          />
          <Button variant="ghost" onClick={() => addItem("work_chores")} className="rounded-full text-[#59745D] mt-2" data-testid="add-work-chore">
            <Plus size={14} className="mr-1"/> Add task
          </Button>
        </Card>

        {/* Notes */}
        <Card className="lg:col-span-3" data-testid="notes-card">
          <Eyebrow>One small note to tomorrow you</Eyebrow>
          <Textarea
            value={plan.notes}
            onChange={(e) => setPlan({ ...plan, notes: e.target.value })}
            placeholder="A reminder, an intention, a kind word…"
            className="mt-2"
            rows={3}
            data-testid="plan-notes"
          />
        </Card>

        {/* Time blocks */}
        <Card className="lg:col-span-3" data-testid="time-blocks-card">
          <div className="flex items-center gap-2 mb-1">
            <Clock size={18} strokeWidth={1.5} className="text-[#59745D]"/>
            <Eyebrow>The shape of the day</Eyebrow>
          </div>
          <p className="text-sm text-[#9A9F9D] mb-4">
            Hour by hour from {fmtHour(plan.wake_target || "06:30")} to {fmtHour(plan.sleep_target || "23:00")}. Leave blank where flexibility lives.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {slots.map(h => (
              <div key={h} className="flex items-center gap-3 px-3 py-2 rounded-2xl bg-[#F4F1EA]" data-testid={`time-block-${h}`}>
                <span className="font-serif text-sm text-[#A3897C] w-14 shrink-0">{fmtHour(h)}</span>
                <Input
                  value={blockMap[h] || ""}
                  onChange={(e) => setBlock(h, e.target.value)}
                  placeholder="—"
                  className="bg-white border-0 rounded-full"
                />
              </div>
            ))}
          </div>
        </Card>
      </div>
    </Container>
  );
}

function ChoreList({ items, field, onUpdate, onRemove, placeholder, testid }) {
  return (
    <div className="space-y-2">
      {items.map((c, i) => (
        <div key={i} className="flex items-center gap-2" data-testid={`${testid}-chore-${i}`}>
          <input type="checkbox" checked={c.done}
            onChange={(e) => onUpdate(field, i, { done: e.target.checked })}
            className="w-4 h-4 accent-[#59745D]"
          />
          <Input
            value={c.text}
            onChange={(e) => onUpdate(field, i, { text: e.target.value })}
            placeholder={placeholder}
            className="rounded-full flex-1"
          />
          <button onClick={() => onRemove(field, i)} className="text-[#9A9F9D] hover:text-[#B85C50]"><X size={15}/></button>
        </div>
      ))}
      {items.length === 0 && <p className="text-xs text-[#9A9F9D] italic">Nothing yet.</p>}
    </div>
  );
}
