import React, { useEffect, useMemo, useState } from "react";
import { api } from "../../lib/api";
import { Card, Eyebrow } from "../Layout";
import { Button } from "../ui/button";
import { Link } from "react-router-dom";
import {
  Star, CheckCircle2, Circle, Plus, Sun, Dumbbell, Home, Briefcase,
  ArrowRight, X,
} from "lucide-react";
import { toast } from "sonner";

const todayISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const blankPlan = {
  date: todayISO(),
  priorities: ["", "", ""],
  priority_status: [
    { done: false, completed_at: null },
    { done: false, completed_at: null },
    { done: false, completed_at: null },
  ],
  morning_routine: [],
  house_chores: [],
  work_chores: [],
  gym_planned: false,
  gym_workout_name: "",
};

export default function TodayPlanCard() {
  const [plan, setPlan] = useState(null);
  const [saving, setSaving] = useState(false);
  const date = todayISO();

  const load = async () => {
    try {
      const { data } = await api.get(`/day-plans/${date}`);
      // Normalise — keep all required arrays present
      setPlan({
        ...blankPlan,
        ...data,
        priorities: (data.priorities || ["", "", ""]).slice(0, 3).concat(["", "", ""]).slice(0, 3),
        priority_status: (data.priority_status || []).slice(0, 3).concat([
          { done: false, completed_at: null },
          { done: false, completed_at: null },
          { done: false, completed_at: null },
        ]).slice(0, 3),
        morning_routine: data.morning_routine || [],
        house_chores: data.house_chores || [],
        work_chores: data.work_chores || [],
      });
    } catch (e) {
      // graceful fallback
      setPlan(blankPlan);
    }
  };

  useEffect(() => { load(); }, []);

  const persist = async (next) => {
    setPlan(next);
    setSaving(true);
    try {
      await api.put(`/day-plans/${date}`, next);
    } catch {
      toast.error("Couldn't save. Try again.");
      load(); // re-sync from server
    } finally {
      setSaving(false);
    }
  };

  const togglePriority = (i) => {
    if (!plan.priorities[i]?.trim()) return; // can't tick empty
    const ps = [...(plan.priority_status || [])];
    const wasDone = ps[i]?.done;
    ps[i] = { done: !wasDone, completed_at: !wasDone ? new Date().toISOString() : null };
    persist({ ...plan, priority_status: ps });
  };

  const toggleChore = (field, i) => {
    const arr = [...plan[field]];
    arr[i] = { ...arr[i], done: !arr[i].done };
    persist({ ...plan, [field]: arr });
  };

  const addChore = (field) => {
    const text = window.prompt(`Add ${field === "house_chores" ? "house chore" : field === "work_chores" ? "work task" : "morning routine item"}:`);
    if (!text || !text.trim()) return;
    const arr = [...(plan[field] || []), { text: text.trim(), done: false }];
    persist({ ...plan, [field]: arr });
  };

  const removeChore = (field, i) => {
    const arr = plan[field].filter((_, idx) => idx !== i);
    persist({ ...plan, [field]: arr });
  };

  const setPriorityText = (i, text) => {
    const next = [...plan.priorities];
    next[i] = text;
    setPlan({ ...plan, priorities: next });
  };

  const blurPriority = () => persist(plan);

  // Stats
  const stats = useMemo(() => {
    if (!plan) return { done: 0, total: 0 };
    let done = 0, total = 0;
    plan.priorities.forEach((p, i) => {
      if (p?.trim()) {
        total++;
        if (plan.priority_status?.[i]?.done) done++;
      }
    });
    [...(plan.morning_routine || []), ...(plan.house_chores || []), ...(plan.work_chores || [])].forEach(c => {
      if (c.text?.trim()) {
        total++;
        if (c.done) done++;
      }
    });
    return { done, total };
  }, [plan]);

  if (!plan) return null;

  const hasAnything =
    plan.priorities.some(p => p?.trim()) ||
    (plan.morning_routine || []).some(c => c.text?.trim()) ||
    (plan.house_chores || []).some(c => c.text?.trim()) ||
    (plan.work_chores || []).some(c => c.text?.trim()) ||
    plan.gym_planned;

  return (
    <Card className="md:col-span-3 bg-white border-sand" data-testid="today-plan-card">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Eyebrow>Today's plan</Eyebrow>
          <p className="font-serif text-2xl text-[#2D312E] mt-1 leading-tight">
            {hasAnything ? "Three things, then the rest." : "Set today's three. Then everything else gets easier."}
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {stats.total > 0 && (
            <div className="hidden sm:flex flex-col items-end" data-testid="today-plan-progress">
              <p className="text-[10px] uppercase tracking-widest text-[#9A9F9D]">Progress</p>
              <p className="font-serif text-lg text-[#2D312E] leading-none mt-1">
                {stats.done}<span className="text-[#9A9F9D] text-sm"> / {stats.total}</span>
              </p>
            </div>
          )}
          <Link
            to="/tomorrow"
            className="text-xs text-[#59745D] hover:underline underline-offset-4 inline-flex items-center gap-1"
            title="Edit the full day plan on Tomorrow page"
          >
            Edit full plan <ArrowRight size={11} strokeWidth={1.5}/>
          </Link>
        </div>
      </div>

      {stats.total > 0 && (
        <div className="mt-4 h-1.5 bg-[#F4F1EA] rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-[#59745D] to-[#A3B58E] transition-all duration-500"
            style={{ width: `${(stats.done / stats.total) * 100}%` }}
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mt-5">
        {/* Top 3 priorities */}
        <div className="space-y-2 lg:col-span-3">
          <div className="flex items-center gap-2">
            <Star size={13} strokeWidth={1.5} className="text-[#C27A62]"/>
            <p className="text-[10px] uppercase tracking-widest text-[#9A9F9D]">Top 3 priorities</p>
          </div>
          {plan.priorities.map((p, i) => {
            const status = plan.priority_status?.[i] || { done: false };
            const empty = !p?.trim();
            return (
              <div key={i} className="flex items-start gap-2 group" data-testid={`today-priority-${i}`}>
                <button
                  onClick={() => togglePriority(i)}
                  disabled={empty}
                  className={`mt-2.5 shrink-0 transition-colors ${empty ? "text-[#E8E2D2] cursor-not-allowed" : status.done ? "text-[#59745D]" : "text-[#9A9F9D] hover:text-[#59745D]"}`}
                  title={empty ? "Type a priority first" : status.done ? "Mark not done" : "Mark done"}
                  data-testid={`priority-tick-${i}`}
                >
                  {status.done ? <CheckCircle2 size={18} strokeWidth={1.5}/> : <Circle size={18} strokeWidth={1.5}/>}
                </button>
                <div className="flex-1">
                  <input
                    value={p}
                    onChange={(e) => setPriorityText(i, e.target.value)}
                    onBlur={blurPriority}
                    onKeyDown={(e) => { if (e.key === "Enter") e.target.blur(); }}
                    placeholder={`Priority ${i + 1}…`}
                    className={`w-full bg-transparent border-0 border-b border-sand focus:outline-none focus:border-[#59745D] py-2 text-[15px] ${
                      status.done ? "line-through text-[#9A9F9D]" : "text-[#2D312E]"
                    } placeholder:text-[#C9C4B5]`}
                    data-testid={`priority-input-${i}`}
                  />
                  {status.done && status.completed_at && (
                    <p className="text-[10px] text-[#9A9F9D] mt-0.5" data-testid={`priority-completed-at-${i}`}>
                      Done · {new Date(status.completed_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Morning routine */}
        <ChoreColumn
          title="Morning routine"
          icon={<Sun size={13} strokeWidth={1.5} className="text-[#E5A85C]"/>}
          items={plan.morning_routine}
          onToggle={(i) => toggleChore("morning_routine", i)}
          onAdd={() => addChore("morning_routine")}
          onRemove={(i) => removeChore("morning_routine", i)}
          field="morning"
        />

        {/* House chores */}
        <ChoreColumn
          title="House"
          icon={<Home size={13} strokeWidth={1.5} className="text-[#A3897C]"/>}
          items={plan.house_chores}
          onToggle={(i) => toggleChore("house_chores", i)}
          onAdd={() => addChore("house_chores")}
          onRemove={(i) => removeChore("house_chores", i)}
          field="house"
        />

        {/* Work tasks */}
        <ChoreColumn
          title="Work"
          icon={<Briefcase size={13} strokeWidth={1.5} className="text-[#59745D]"/>}
          items={plan.work_chores}
          onToggle={(i) => toggleChore("work_chores", i)}
          onAdd={() => addChore("work_chores")}
          onRemove={(i) => removeChore("work_chores", i)}
          field="work"
        />
      </div>

      {/* Gym status */}
      {plan.gym_planned && (
        <div className="mt-5 inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#EDF1ED] border border-[#D8E2D9]" data-testid="today-gym-badge">
          <Dumbbell size={14} strokeWidth={1.5} className="text-[#59745D]"/>
          <span className="text-sm text-[#2D312E]">Gym today{plan.gym_workout_name ? ` — ${plan.gym_workout_name}` : ""}</span>
        </div>
      )}

      {saving && (
        <p className="text-[10px] text-[#9A9F9D] mt-3" data-testid="today-plan-saving">Saving…</p>
      )}
    </Card>
  );
}

function ChoreColumn({ title, icon, items, onToggle, onAdd, onRemove, field }) {
  const list = items || [];
  return (
    <div className="space-y-1.5" data-testid={`today-chore-col-${field}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon}
          <p className="text-[10px] uppercase tracking-widest text-[#9A9F9D]">{title}</p>
          {list.length > 0 && (
            <span className="text-[10px] text-[#9A9F9D]">
              {list.filter(c => c.done).length}/{list.length}
            </span>
          )}
        </div>
        <button
          onClick={onAdd}
          className="text-[#9A9F9D] hover:text-[#59745D] transition-colors"
          title={`Add ${title.toLowerCase()} item`}
          data-testid={`today-chore-add-${field}`}
        >
          <Plus size={14} strokeWidth={1.5}/>
        </button>
      </div>
      {list.length === 0 ? (
        <p className="text-xs text-[#C9C4B5] italic py-1">Nothing yet.</p>
      ) : (
        list.map((c, i) => (
          <div key={i} className="flex items-center gap-2 group" data-testid={`today-chore-${field}-${i}`}>
            <button
              onClick={() => onToggle(i)}
              className={`shrink-0 transition-colors ${c.done ? "text-[#59745D]" : "text-[#9A9F9D] hover:text-[#59745D]"}`}
              data-testid={`today-chore-tick-${field}-${i}`}
            >
              {c.done ? <CheckCircle2 size={15} strokeWidth={1.5}/> : <Circle size={15} strokeWidth={1.5}/>}
            </button>
            <span className={`flex-1 text-sm leading-snug ${c.done ? "line-through text-[#9A9F9D]" : "text-[#2D312E]"}`}>
              {c.text}
            </span>
            <button
              onClick={() => onRemove(i)}
              className="opacity-0 group-hover:opacity-100 text-[#9A9F9D] hover:text-[#B85C50] transition-opacity"
              title="Remove"
              data-testid={`today-chore-remove-${field}-${i}`}
            >
              <X size={12} strokeWidth={1.5}/>
            </button>
          </div>
        ))
      )}
    </div>
  );
}
