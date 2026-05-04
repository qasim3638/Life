import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { Sparkles, X, Droplets, Dumbbell, HeartPulse, MoonStar, BookOpen, Target, CalendarDays } from "lucide-react";

// Per-day dismiss key so alerts reappear tomorrow
const dismissKey = () => `companion-alerts-dismissed-${new Date().toDateString()}`;

const TONE_STYLES = {
  practical: "from-[#E8F0E9] via-white",
  nudge: "from-[#F4F1EA] via-white",
  soft: "from-[#FAF6EC] via-white",
  spiritual: "from-[#F5EEE3] via-white",
};

function iconFor(id) {
  if (id.startsWith("rain-")) return Droplets;
  if (id.startsWith("workout-") || id === "no-workout-ever") return Dumbbell;
  if (id.startsWith("journal-")) return HeartPulse;
  if (id.startsWith("prayer-")) return MoonStar;
  if (id === "sunday-review") return BookOpen;
  if (id === "no-priorities") return Target;
  if (id.startsWith("event-")) return CalendarDays;
  return Sparkles;
}

export default function CompanionAlerts() {
  const [alerts, setAlerts] = useState([]);
  const [dismissed, setDismissed] = useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem(dismissKey()) || "[]")); }
    catch { return new Set(); }
  });

  useEffect(() => {
    api.get("/companion/alerts").then(r => setAlerts(r.data || [])).catch(() => {});
  }, []);

  const dismiss = (id) => {
    const next = new Set(dismissed);
    next.add(id);
    setDismissed(next);
    try { localStorage.setItem(dismissKey(), JSON.stringify([...next])); } catch {}
  };

  const visible = alerts.filter(a => !dismissed.has(a.id));
  if (visible.length === 0) return null;

  return (
    <div className="mb-8 grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="companion-alerts">
      {visible.map(a => {
        const Icon = iconFor(a.id);
        const tone = TONE_STYLES[a.tone] || TONE_STYLES.soft;
        return (
          <div
            key={a.id}
            className={`group relative rounded-3xl border border-sand bg-gradient-to-br ${tone} to-transparent px-5 py-4 flex items-start gap-3 transition-all hover:border-[#59745D]/30`}
            data-testid={`alert-${a.id}`}
          >
            <div className="w-10 h-10 rounded-full bg-white border border-sand flex items-center justify-center shrink-0">
              <Icon size={17} strokeWidth={1.5} className="text-[#59745D]"/>
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-serif text-lg leading-snug text-[#2D312E]">{a.title}</p>
              <p className="text-sm text-[#6B7270] mt-0.5 leading-relaxed">{a.body}</p>
              {a.cta && (
                <Link
                  to={a.cta.href}
                  className="inline-block mt-2 text-xs uppercase tracking-widest text-[#59745D] hover:underline underline-offset-4"
                  data-testid={`alert-cta-${a.id}`}
                >
                  {a.cta.label} →
                </Link>
              )}
            </div>
            <button
              onClick={() => dismiss(a.id)}
              className="text-[#9A9F9D] hover:text-[#2D312E] opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
              title="Dismiss"
              data-testid={`dismiss-alert-${a.id}`}
            >
              <X size={14} strokeWidth={1.5}/>
            </button>
          </div>
        );
      })}
    </div>
  );
}
