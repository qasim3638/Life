import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Container, Card, Eyebrow, PageHeader } from "../components/Layout";
import { Button } from "../components/ui/button";
import {
  BookOpen, Sparkles, Flame, HeartPulse, Timer, Shield as ShieldIcon,
  Users, Target, ChevronDown, ChevronUp,
} from "lucide-react";
import { toast } from "sonner";

const HERO_IMG = "https://static.prod-images.emergentagent.com/jobs/b8c548de-315f-4118-954b-1d59454f577f/images/252006b3fbe027b3d88a8673d327c4616289615eec678e0bbb491a6b1e1f603e.png";

function fmtRange(startISO, endISO) {
  try {
    const s = new Date(startISO + "T00:00:00");
    const e = new Date(endISO + "T00:00:00");
    const sameMonth = s.getMonth() === e.getMonth();
    const sPart = s.toLocaleDateString(undefined, { month: "long", day: "numeric" });
    const ePart = e.toLocaleDateString(undefined, {
      month: sameMonth ? undefined : "long",
      day: "numeric",
      year: "numeric",
    });
    return `${sPart} – ${ePart}`;
  } catch {
    return `${startISO} – ${endISO}`;
  }
}

function DataStat({ icon: Icon, color, value, label, testid }) {
  return (
    <div className="bg-white rounded-2xl border border-sand p-4" data-testid={testid}>
      <Icon size={16} strokeWidth={1.5} className={color} />
      <p className="font-serif text-3xl text-[#2D312E] mt-2 leading-none">{value}</p>
      <p className="text-xs text-[#6B7270] mt-1 leading-snug">{label}</p>
    </div>
  );
}

function ReviewCard({ review, featured = false }) {
  const [open, setOpen] = useState(featured);
  const d = review.data || {};
  return (
    <Card
      className={featured ? "md:col-span-3 bg-gradient-to-br from-[#FAF6EC] to-white border-0" : "md:col-span-3"}
      data-testid={featured ? "review-featured" : `review-${review.week_start}`}
    >
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <Eyebrow>{featured ? "This week's reflection" : "Past week"}</Eyebrow>
          <h2 className="font-serif text-2xl md:text-3xl text-[#2D312E] leading-snug mt-1">
            {fmtRange(review.week_start, review.week_end)}
          </h2>
        </div>
        {!featured && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setOpen(o => !o)}
            className="rounded-full border-sand text-[#6B7270] hover:bg-[#F4F1EA]"
            data-testid={`toggle-${review.week_start}`}
          >
            {open ? <ChevronUp size={14} strokeWidth={1.5} className="mr-1" /> : <ChevronDown size={14} strokeWidth={1.5} className="mr-1" />}
            {open ? "Collapse" : "Read"}
          </Button>
        )}
      </div>

      {open && (
        <>
          <p
            className="font-serif text-lg md:text-xl text-[#2D312E] mt-5 leading-relaxed whitespace-pre-wrap max-w-3xl"
            data-testid={`review-text-${review.week_start}`}
          >
            {review.text}
          </p>

          <div className="mt-7 grid grid-cols-2 md:grid-cols-5 gap-3">
            <DataStat
              icon={Flame} color="text-[#C27A62]"
              value={d.workout_count ?? 0}
              label={`workout${d.workout_count === 1 ? "" : "s"} · ${d.workout_minutes ?? 0} min`}
              testid={`stat-workouts-${review.week_start}`}
            />
            <DataStat
              icon={HeartPulse} color="text-[#59745D]"
              value={d.journal_count ?? 0}
              label={d.average_mood ? `entries · mood ${d.average_mood}/5` : "journal entries"}
              testid={`stat-journal-${review.week_start}`}
            />
            <DataStat
              icon={Timer} color="text-[#A3897C]"
              value={d.focus_minutes ?? 0}
              label={`focus min · ${d.focus_sessions ?? 0} sessions`}
              testid={`stat-focus-${review.week_start}`}
            />
            <DataStat
              icon={ShieldIcon} color="text-[#59745D]"
              value={(d.addictions || []).reduce((sum, a) => sum + (a.slips_this_week || 0), 0)}
              label="slips this week"
              testid={`stat-slips-${review.week_start}`}
            />
            <DataStat
              icon={Target} color="text-[#C27A62]"
              value={`${d.plan_chores_done ?? 0}/${d.plan_chores_total ?? 0}`}
              label="plan items tended"
              testid={`stat-plan-${review.week_start}`}
            />
          </div>

          {(d.family_memories_saved?.length > 0) && (
            <div className="mt-5 flex items-start gap-2">
              <Users size={14} strokeWidth={1.5} className="text-[#A3897C] mt-1 shrink-0" />
              <p className="text-sm text-[#6B7270] leading-relaxed">
                <span className="text-[10px] uppercase tracking-[0.25em] text-[#9A9F9D] mr-2">Remembered</span>
                {d.family_memories_saved.join(" · ")}
              </p>
            </div>
          )}
        </>
      )}
    </Card>
  );
}

export default function Review() {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/sunday-reviews");
      setReviews(data || []);
    } catch {
      toast.error("Could not load reviews.");
    }
  };

  useEffect(() => { load(); }, []);

  const generate = async (regenerate = false) => {
    setLoading(true);
    try {
      await api.post(`/ai/sunday-review${regenerate ? "?regenerate=true" : ""}`, {});
      await load();
      toast.success(regenerate ? "Reflection rewritten." : "Your week is reflected on.");
    } catch {
      toast.error("AI is resting. Try again shortly.");
    } finally {
      setLoading(false);
    }
  };

  // Work out if current week's review already exists
  const today = new Date();
  const dayIdx = today.getDay(); // 0 Sun .. 6 Sat
  const daysFromMonday = (dayIdx + 6) % 7;
  const monday = new Date(today);
  monday.setDate(today.getDate() - daysFromMonday);
  const mondayISO = monday.toISOString().slice(0, 10);
  const hasCurrent = reviews.some(r => r.week_start === mondayISO);

  const latest = reviews[0];
  const past = reviews.slice(1);

  return (
    <Container>
      <PageHeader
        eyebrow="Sunday Rhythm"
        title="What your week said about you."
        subtitle="An honest, gentle weekly reflection — written from your actual days, not a template."
        image={HERO_IMG}
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="md:col-span-3 bg-[#F4F1EA] border-0" data-testid="card-generate">
          <div className="flex items-start gap-4 flex-wrap">
            <div className="w-10 h-10 rounded-full bg-white border border-sand flex items-center justify-center shrink-0">
              <BookOpen size={18} strokeWidth={1.5} className="text-[#59745D]" />
            </div>
            <div className="flex-1 min-w-[200px]">
              <Eyebrow>{hasCurrent ? "This week, reflected" : "This week, waiting"}</Eyebrow>
              <p className="font-serif text-xl md:text-2xl text-[#2D312E] leading-snug mt-1">
                {hasCurrent
                  ? "Your reflection for the week is below. You can let it rewrite itself if the week isn't closed yet."
                  : "Close the week with one quiet paragraph. It only writes what your data actually shows."}
              </p>
            </div>
            <div className="flex gap-2">
              {!hasCurrent && (
                <Button
                  onClick={() => generate(false)}
                  disabled={loading}
                  className="rounded-full bg-[#59745D] hover:bg-[#4A604D]"
                  data-testid="generate-review-btn"
                >
                  <Sparkles size={14} strokeWidth={1.5} className="mr-1" />
                  {loading ? "Listening to your week…" : "Write this week's reflection"}
                </Button>
              )}
              {hasCurrent && (
                <Button
                  onClick={() => generate(true)}
                  disabled={loading}
                  variant="outline"
                  className="rounded-full border-[#59745D] text-[#59745D] hover:bg-[#59745D] hover:text-white"
                  data-testid="regenerate-review-btn"
                >
                  <Sparkles size={14} strokeWidth={1.5} className="mr-1" />
                  {loading ? "Rewriting…" : "Rewrite it"}
                </Button>
              )}
            </div>
          </div>
        </Card>

        {latest && <ReviewCard review={latest} featured />}

        {past.length > 0 && (
          <div className="md:col-span-3 mt-4">
            <Eyebrow>Earlier weeks</Eyebrow>
          </div>
        )}

        {past.map(r => <ReviewCard key={r.week_start} review={r} />)}

        {reviews.length === 0 && (
          <Card className="md:col-span-3 text-center py-14" data-testid="review-empty">
            <p className="font-serif text-2xl text-[#2D312E]">No weeks reflected on yet.</p>
            <p className="text-sm text-[#6B7270] mt-3 max-w-md mx-auto leading-relaxed">
              Your first Sunday reflection will appear here once you generate it above.
            </p>
          </Card>
        )}
      </div>
    </Container>
  );
}
