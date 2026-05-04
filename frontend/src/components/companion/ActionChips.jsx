import React, { useState } from "react";
import { api } from "../../lib/api";
import { Check, X, CalendarDays, Clock, Star, ListTodo, Dumbbell, HeartPulse } from "lucide-react";
import { toast } from "sonner";

const ICON_BY_TYPE = {
  add_time_block: Clock,
  add_event: CalendarDays,
  add_priority: Star,
  add_chore: ListTodo,
  log_workout: Dumbbell,
  log_journal: HeartPulse,
};

function humanise(a) {
  switch (a.type) {
    case "add_time_block":
      return `${a.text} at ${a.hour} on ${a.date}`;
    case "add_event":
      return `Event "${a.title}" on ${a.date}`;
    case "add_priority":
      return `Priority "${a.text}" for ${a.date}`;
    case "add_chore":
      return `${a.kind} chore "${a.text}"${a.date ? ` on ${a.date}` : ""}`;
    case "log_workout":
      return `Log workout: ${a.name} (${a.duration_min} min)${a.date ? ` — ${a.date}` : ""}`;
    case "log_journal":
      return `Journal entry${a.mood ? ` (mood ${a.mood}/5)` : ""}: "${(a.entry || a.gratitude || "").slice(0, 60)}…"`;
    default:
      return a.type;
  }
}

export default function ActionChips({ message, onMessageUpdate }) {
  const [busy, setBusy] = useState(null);
  const actions = message.actions || [];
  if (actions.length === 0) return null;

  const handle = async (action, verb) => {
    setBusy(action.id);
    try {
      const { data } = await api.post(`/companion/messages/${message.id}/actions/${action.id}/${verb}`);
      const updated = {
        ...message,
        actions: actions.map(a => a.id === action.id ? { ...a, ...data.action } : a),
      };
      onMessageUpdate(updated);
      if (verb === "apply") toast.success(data.action?.result || "Done");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Couldn't apply");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="mt-3 space-y-2" data-testid={`actions-${message.id}`}>
      {actions.map(a => {
        const Icon = ICON_BY_TYPE[a.type] || ListTodo;
        const isPending = a.status === "pending";
        const isApplied = a.status === "applied";
        const isCancelled = a.status === "cancelled";
        const loading = busy === a.id;
        return (
          <div
            key={a.id}
            className={`rounded-2xl border px-3 py-2 flex items-center gap-3 text-sm transition-colors ${
              isApplied ? "bg-[#59745D]/10 border-[#59745D]/30 text-[#2D312E]"
              : isCancelled ? "bg-[#F4F1EA] border-sand text-[#9A9F9D] line-through"
              : "bg-white border-sand text-[#2D312E]"
            }`}
            data-testid={`action-${a.id}`}
          >
            <Icon size={14} strokeWidth={1.5} className={isApplied ? "text-[#59745D]" : isCancelled ? "text-[#9A9F9D]" : "text-[#C27A62]"}/>
            <span className="flex-1 leading-snug">{humanise(a)}</span>
            {isPending && (
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => handle(a, "apply")}
                  disabled={loading}
                  className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-[#59745D] text-white hover:bg-[#4A604D] disabled:opacity-50 text-xs font-medium"
                  data-testid={`apply-${a.id}`}
                >
                  <Check size={12} strokeWidth={2}/> Apply
                </button>
                <button
                  onClick={() => handle(a, "cancel")}
                  disabled={loading}
                  className="inline-flex items-center gap-1 px-3 py-1 rounded-full border border-sand text-[#6B7270] hover:bg-[#F4F1EA] disabled:opacity-50 text-xs"
                  data-testid={`cancel-${a.id}`}
                >
                  <X size={12} strokeWidth={2}/>
                </button>
              </div>
            )}
            {isApplied && (
              <span className="text-[10px] uppercase tracking-widest text-[#59745D] shrink-0">
                <Check size={11} strokeWidth={2} className="inline mr-0.5"/> Applied
              </span>
            )}
            {isCancelled && (
              <span className="text-[10px] uppercase tracking-widest text-[#9A9F9D] shrink-0">Skipped</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
