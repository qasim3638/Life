import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Container, Card, Eyebrow, PageHeader } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Sparkles, Flame, HeartPulse, CalendarDays, Quote as QuoteIcon, Trophy, BookOpen } from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import ProtectedCard from "../components/today/ProtectedCard";
import DailyBriefCard from "../components/today/DailyBriefCard";
import StreakProtectorCard from "../components/today/StreakProtectorCard";
import LifeArcCard from "../components/today/LifeArcCard";
import WeeklyLetterCard from "../components/today/WeeklyLetterCard";

const HERO_IMG = "https://static.prod-images.emergentagent.com/jobs/b8c548de-315f-4118-954b-1d59454f577f/images/252006b3fbe027b3d88a8673d327c4616289615eec678e0bbb491a6b1e1f603e.png";

const AGE_NOW = 40;
const TARGET_AGE = 80;

export default function Today() {
  const [motivation, setMotivation] = useState("");
  const [loading, setLoading] = useState(false);
  const [quote, setQuote] = useState(null);
  const [events, setEvents] = useState([]);
  const [logs, setLogs] = useState([]);
  const [journal, setJournal] = useState([]);
  const [goals, setGoals] = useState([]);
  const [streaks, setStreaks] = useState({ workout_streak: 0, journal_streak: 0, workout_today: false, journal_today: false });
  const [brief, setBrief] = useState("");
  const [briefLoading, setBriefLoading] = useState(false);
  const [echo, setEcho] = useState("");
  const [addictions, setAddictions] = useState([]);
  const [focusToday, setFocusToday] = useState({ today_focus_min: 0 });
  const [weekReview, setWeekReview] = useState(null);

  // Echo of yesterday — auto-loads on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.post("/ai/echo-yesterday", {});
        if (!cancelled) setEcho(data.text || "");
      } catch { /* silent */ }
    })();
    return () => { cancelled = true; };
  }, []);

  // Sobriety + focus side-by-side
  useEffect(() => {
    const tz_offset_min = -new Date().getTimezoneOffset();
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, "0");
    const dd = String(today.getDate()).padStart(2, "0");
    const localDate = `${yyyy}-${mm}-${dd}`;
    Promise.all([
      api.get("/addictions"),
      api.get(`/focus-stats?date=${localDate}&tz_offset_min=${tz_offset_min}`),
    ]).then(([a, f]) => {
      setAddictions(a.data);
      setFocusToday(f.data);
    }).catch(() => {});
  }, []);
  // Sunday reflection availability — only fetch on Sunday
  useEffect(() => {
    if (new Date().getDay() !== 0) return;
    api.get("/sunday-reviews/latest").then(({ data }) => {
      setWeekReview(data && data.week_start ? data : null);
    }).catch(() => {});
  }, []);

  const [letter, setLetter] = useState("");
  const [letterLoading, setLetterLoading] = useState(false);

  const load = async () => {
    try {
      const [q, e, l, j, g, s] = await Promise.all([
        api.get("/quotes"),
        api.get("/events"),
        api.get("/workout-logs"),
        api.get("/journal-entries"),
        api.get("/life-goals"),
        api.get("/streaks"),
      ]);
      setQuote(q.data[Math.floor(Math.random() * q.data.length)]);
      setEvents(e.data);
      setLogs(l.data);
      setJournal(j.data);
      setGoals(g.data);
      setStreaks(s.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => { load(); }, []);

  const getMotivation = async () => {
    setLoading(true);
    try {
      const { data } = await api.post("/ai/motivation", {
        prompt: "today",
        context: `User is 40. ${logs.length} workouts logged, ${journal.length} journal entries, ${goals.length} life goals planted.`,
      });
      setMotivation(data.text);
    } catch {
      toast.error("AI is resting. Try again shortly.");
    } finally { setLoading(false); }
  };

  const getLetter = async () => {
    setLetterLoading(true);
    try {
      const { data } = await api.post("/ai/weekly-letter", {});
      setLetter(data.text);
    } catch {
      toast.error("AI is resting. Try again shortly.");
    } finally { setLetterLoading(false); }
  };

  const getBrief = async () => {
    setBriefLoading(true);
    try {
      const { data } = await api.post("/ai/daily-brief", {});
      setBrief(data.text);
    } catch {
      toast.error("AI is resting. Try again shortly.");
    } finally { setBriefLoading(false); }
  };

  const today = new Date().toISOString().slice(0, 10);
  const upcoming = events
    .filter(e => e.date >= today)
    .slice(0, 3);

  const todayStr = new Date().toLocaleDateString(undefined, {
    weekday: "long", month: "long", day: "numeric",
  });

  const hourNow = new Date().getHours();
  const isSunday = new Date().getDay() === 0;
  // Monday ISO of current week (for comparing against latest review)
  const _mon = new Date();
  _mon.setDate(_mon.getDate() - ((_mon.getDay() + 6) % 7));
  const currentWeekMondayISO = _mon.toISOString().slice(0, 10);
  const currentWeekReviewed = weekReview && weekReview.week_start === currentWeekMondayISO;
  const showProtector =
    hourNow >= 18 && (!streaks.workout_today || !streaks.journal_today);

  return (
    <Container>
      <PageHeader
        eyebrow={todayStr}
        title="A quiet, grounded beginning."
        subtitle="The next 40 years are built from days like this one."
        image={HERO_IMG}
      />

      {echo && (
        <div className="mb-8 -mt-2 px-6 py-3 rounded-full bg-[#F4F1EA] border border-sand text-sm text-[#6B7270] flex items-center gap-3" data-testid="echo-yesterday">
          <span className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C] shrink-0">Yesterday</span>
          <span className="font-serif text-base text-[#2D312E] leading-snug">{echo}</span>
        </div>
      )}

      {isSunday && (
        <Link to="/review" className="block mb-8 group" data-testid="sunday-banner">
          <div className="px-6 py-4 rounded-3xl bg-gradient-to-r from-[#FAF6EC] via-[#F4F1EA] to-transparent border border-sand flex items-center gap-4 transition-all group-hover:border-[#59745D]/40 group-hover:shadow-sm">
            <div className="w-10 h-10 rounded-full bg-white border border-sand flex items-center justify-center shrink-0">
              <BookOpen size={18} strokeWidth={1.5} className="text-[#59745D]" />
            </div>
            <div className="flex-1">
              <p className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C]">Sunday</p>
              <p className="font-serif text-lg md:text-xl text-[#2D312E] leading-snug mt-0.5">
                {currentWeekReviewed
                  ? "Your week's reflection is ready to read."
                  : "Close the week with a quiet reflection."}
              </p>
            </div>
            <span className="hidden sm:inline text-sm text-[#59745D] font-medium group-hover:underline underline-offset-4">
              {currentWeekReviewed ? "Read it →" : "Open →"}
            </span>
          </div>
        </Link>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <ProtectedCard addictions={addictions} focusToday={focusToday} />

        <DailyBriefCard brief={brief} loading={briefLoading} onGenerate={getBrief} />

        {showProtector && (
          <StreakProtectorCard
            workoutToday={streaks.workout_today}
            journalToday={streaks.journal_today}
          />
        )}

        <LifeArcCard ageNow={AGE_NOW} targetAge={TARGET_AGE} />

        {/* AI motivation */}
        <Card className="md:col-span-2 bg-[#F4F1EA] border-0 relative overflow-hidden" data-testid="card-ai-motivation">
          <Eyebrow>Today's reflection</Eyebrow>
          {motivation ? (
            <p className="font-serif text-2xl md:text-3xl text-[#2D312E] leading-snug mt-2">
              {motivation}
            </p>
          ) : (
            <>
              <p className="font-serif text-2xl md:text-3xl text-[#2D312E] leading-snug mt-2">
                {quote?.text || "Breathe. Begin."}
              </p>
              <p className="text-sm text-[#9A9F9D] mt-3">— {quote?.author || "Rumi"}</p>
            </>
          )}
          <Button
            onClick={getMotivation}
            disabled={loading}
            className="mt-6 rounded-full bg-[#59745D] hover:bg-[#4A604D] text-white"
            data-testid="ai-motivation-btn"
          >
            <Sparkles size={16} strokeWidth={1.5} className="mr-2" />
            {loading ? "Summoning…" : "Give me wisdom for today"}
          </Button>
        </Card>

        {/* Stats bento */}
        <Card data-testid="stat-workouts">
          <div className="flex items-start justify-between">
            <div>
              <Eyebrow>Movement</Eyebrow>
              <p className="font-serif text-4xl text-[#2D312E] mt-1">{logs.length}</p>
              <p className="text-sm text-[#6B7270]">workouts logged</p>
            </div>
            <Flame size={22} strokeWidth={1.5} className="text-[#C27A62]" />
          </div>
        </Card>

        <Card data-testid="stat-journal">
          <div className="flex items-start justify-between">
            <div>
              <Eyebrow>Inner work</Eyebrow>
              <p className="font-serif text-4xl text-[#2D312E] mt-1">{journal.length}</p>
              <p className="text-sm text-[#6B7270]">journal entries</p>
            </div>
            <HeartPulse size={22} strokeWidth={1.5} className="text-[#59745D]" />
          </div>
        </Card>

        <Card data-testid="stat-goals">
          <div className="flex items-start justify-between">
            <div>
              <Eyebrow>Blueprint</Eyebrow>
              <p className="font-serif text-4xl text-[#2D312E] mt-1">{goals.length}</p>
              <p className="text-sm text-[#6B7270]">goals planted</p>
            </div>
            <CalendarDays size={22} strokeWidth={1.5} className="text-[#A3897C]" />
          </div>
        </Card>

        {/* Upcoming */}
        <Card className="md:col-span-2" data-testid="card-upcoming">
          <Eyebrow>Coming up</Eyebrow>
          {upcoming.length === 0 ? (
            <p className="text-[#6B7270] mt-4 leading-relaxed">
              Your calendar is quiet. <Link to="/events" className="text-[#59745D] underline underline-offset-4">Add a meaningful date</Link>.
            </p>
          ) : (
            <ul className="mt-4 divide-y divide-sand">
              {upcoming.map(e => (
                <li key={e.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="font-medium text-[#2D312E]">{e.title}</p>
                    <p className="text-xs uppercase tracking-wider text-[#9A9F9D] mt-1">{e.type}</p>
                  </div>
                  <p className="text-sm text-[#6B7270]">{e.date}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Quote */}
        <Card className="bg-white" data-testid="card-quote">
          <QuoteIcon size={20} strokeWidth={1.5} className="text-[#C27A62]" />
          <p className="font-serif text-xl text-[#2D312E] mt-3 leading-snug">
            {quote?.text}
          </p>
          <p className="text-xs text-[#9A9F9D] mt-3 uppercase tracking-widest">— {quote?.author}</p>
        </Card>

        {/* Streaks */}
        <Card className="md:col-span-2" data-testid="card-streaks">
          <div className="flex items-center gap-2 mb-3">
            <Trophy size={18} strokeWidth={1.5} className="text-[#C27A62]" />
            <Eyebrow>Streaks</Eyebrow>
          </div>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <p className="font-serif text-5xl text-[#2D312E]">{streaks.workout_streak}</p>
              <p className="text-sm text-[#6B7270] mt-1">day{streaks.workout_streak === 1 ? "" : "s"} of movement</p>
              <p className="text-xs text-[#9A9F9D] mt-0.5">{streaks.workout_total_days} total</p>
            </div>
            <div>
              <p className="font-serif text-5xl text-[#2D312E]">{streaks.journal_streak}</p>
              <p className="text-sm text-[#6B7270] mt-1">day{streaks.journal_streak === 1 ? "" : "s"} of reflection</p>
              <p className="text-xs text-[#9A9F9D] mt-0.5">{streaks.journal_total_days} total</p>
            </div>
          </div>
        </Card>

        {/* Weekly letter */}
        <WeeklyLetterCard letter={letter} loading={letterLoading} onGenerate={getLetter} />
      </div>
    </Container>
  );
}
