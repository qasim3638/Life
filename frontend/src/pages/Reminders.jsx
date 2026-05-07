/**
 * RemindersPage — manage reminders + Yaar Whisper Mode global settings.
 *
 * Routes added:  /reminders
 */
import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Bell, Plus, Trash2, Check, Save } from "lucide-react";
import { toast } from "sonner";

const SUMMON_STYLES = [
  { value: "chime", label: "Soft chime only" },
  { value: "chime_name", label: "Chime + name" },
  { value: "name", label: "Name only" },
];

const FALLBACKS = [
  { value: "badge", label: "Quiet badge" },
  { value: "vibrate", label: "Vibration" },
  { value: "silent", label: "Silent" },
];

const GAP_OPTIONS = [10, 20, 30, 60, 120, 300];

function formatLocalDateTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const z = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}`;
}

export default function Reminders() {
  const [list, setList] = useState([]);
  const [settings, setSettings] = useState(null);
  const [draft, setDraft] = useState({
    title: "",
    body: "",
    fire_at: "",
    summon_style: "",
    summon_name: "",
    gap_seconds: "",
    max_attempts: "",
    fallback: "",
  });
  const [savingSettings, setSavingSettings] = useState(false);

  const loadAll = async () => {
    try {
      const [r1, r2] = await Promise.all([
        api.get("/reminders"),
        api.get("/reminders/whisper/settings"),
      ]);
      setList(r1.data || []);
      setSettings(r2.data);
    } catch (e) { /* */ }
  };

  useEffect(() => { loadAll(); }, []);

  const create = async (e) => {
    e.preventDefault();
    if (!draft.title.trim() || !draft.fire_at) {
      toast.error("Title and time required");
      return;
    }
    const fireAtIso = new Date(draft.fire_at).toISOString();
    const payload = { title: draft.title.trim(), body: draft.body.trim(), fire_at: fireAtIso };
    if (draft.summon_style) payload.summon_style = draft.summon_style;
    if (draft.summon_name.trim()) payload.summon_name = draft.summon_name.trim();
    if (draft.gap_seconds) payload.gap_seconds = parseInt(draft.gap_seconds, 10);
    if (draft.max_attempts) payload.max_attempts = parseInt(draft.max_attempts, 10);
    if (draft.fallback) payload.fallback = draft.fallback;
    try {
      await api.post("/reminders", payload);
      toast.success("Reminder set");
      setDraft({ title: "", body: "", fire_at: "", summon_style: "", summon_name: "", gap_seconds: "", max_attempts: "", fallback: "" });
      loadAll();
    } catch {
      toast.error("Couldn't save");
    }
  };

  const remove = async (id) => {
    try {
      await api.delete(`/reminders/${id}`);
      setList((l) => l.filter((r) => r.id !== id));
    } catch {}
  };

  const saveSettings = async (next) => {
    setSavingSettings(true);
    try {
      const { data } = await api.put("/reminders/whisper/settings", next);
      setSettings(data);
      toast.success("Whisper updated");
    } catch {
      toast.error("Couldn't save");
    } finally {
      setSavingSettings(false);
    }
  };

  if (!settings) return <div className="p-8 text-[#6B7270]">Loading…</div>;

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 space-y-10" data-testid="reminders-page">
      <header>
        <p className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C]">Yaar</p>
        <h1 className="font-serif text-4xl text-[#2D312E] mt-1">Reminders & Whisper</h1>
        <p className="text-sm text-[#6B7270] mt-2 leading-relaxed">
          Yaar gently chimes until you respond. He never blasts a reminder out loud first.
        </p>
      </header>

      {/* Whisper defaults */}
      <section className="rounded-3xl bg-white border border-sand p-6 space-y-4" data-testid="whisper-settings">
        <h2 className="font-serif text-2xl text-[#2D312E]">How Yaar summons you</h2>

        <Field label="Summon style">
          <Select
            value={settings.summon_style}
            onChange={(v) => saveSettings({ ...settings, summon_style: v })}
            options={SUMMON_STYLES}
            disabled={savingSettings}
            testid="summon-style-select"
          />
        </Field>

        <Field label="Summon name (try Bhai, Jaan, Boss…)">
          <input
            type="text"
            value={settings.summon_name}
            onChange={(e) => setSettings({ ...settings, summon_name: e.target.value })}
            onBlur={() => saveSettings(settings)}
            className="w-full px-3 py-2 rounded-xl border border-sand bg-[#FDFBF7] text-sm focus:outline-none focus:border-[#59745D]"
            data-testid="summon-name-input"
          />
        </Field>

        <Field label="Wait between chimes">
          <Select
            value={String(settings.gap_seconds)}
            onChange={(v) => saveSettings({ ...settings, gap_seconds: parseInt(v, 10) })}
            options={GAP_OPTIONS.map((s) => ({ value: String(s), label: s < 60 ? `${s}s` : `${s / 60}m` }))}
            disabled={savingSettings}
            testid="gap-seconds-select"
          />
        </Field>

        <Field label="Max attempts before giving up">
          <input
            type="number"
            min="1" max="15"
            value={settings.max_attempts}
            onChange={(e) => setSettings({ ...settings, max_attempts: parseInt(e.target.value || "1", 10) })}
            onBlur={() => saveSettings(settings)}
            className="w-full px-3 py-2 rounded-xl border border-sand bg-[#FDFBF7] text-sm focus:outline-none focus:border-[#59745D]"
            data-testid="max-attempts-input"
          />
        </Field>

        <Field label="If you never respond">
          <Select
            value={settings.fallback}
            onChange={(v) => saveSettings({ ...settings, fallback: v })}
            options={FALLBACKS}
            disabled={savingSettings}
            testid="fallback-select"
          />
        </Field>
      </section>

      {/* Create */}
      <section className="rounded-3xl bg-white border border-sand p-6">
        <h2 className="font-serif text-2xl text-[#2D312E] mb-4">New reminder</h2>
        <form onSubmit={create} className="space-y-3" data-testid="reminder-create-form">
          <input
            type="text"
            placeholder="What should Yaar remind you of?"
            value={draft.title}
            onChange={(e) => setDraft({ ...draft, title: e.target.value })}
            required
            className="w-full px-3 py-2.5 rounded-xl border border-sand bg-[#FDFBF7] text-[#2D312E] focus:outline-none focus:border-[#59745D]"
            data-testid="reminder-title-input"
          />
          <textarea
            placeholder="Optional details Yaar will read out loud…"
            value={draft.body}
            onChange={(e) => setDraft({ ...draft, body: e.target.value })}
            rows={2}
            className="w-full px-3 py-2.5 rounded-xl border border-sand bg-[#FDFBF7] text-sm focus:outline-none focus:border-[#59745D]"
            data-testid="reminder-body-input"
          />
          <input
            type="datetime-local"
            value={draft.fire_at}
            onChange={(e) => setDraft({ ...draft, fire_at: e.target.value })}
            required
            className="w-full px-3 py-2.5 rounded-xl border border-sand bg-[#FDFBF7] text-[#2D312E] focus:outline-none focus:border-[#59745D]"
            data-testid="reminder-fire-at-input"
          />
          <details className="text-sm">
            <summary className="text-[#59745D] cursor-pointer select-none">Override Whisper for this one</summary>
            <div className="grid grid-cols-2 gap-2 mt-3">
              <Select
                value={draft.summon_style}
                onChange={(v) => setDraft({ ...draft, summon_style: v })}
                options={[{ value: "", label: "Default style" }, ...SUMMON_STYLES]}
              />
              <input
                type="text"
                placeholder="Custom name"
                value={draft.summon_name}
                onChange={(e) => setDraft({ ...draft, summon_name: e.target.value })}
                className="px-3 py-2 rounded-xl border border-sand bg-[#FDFBF7] text-sm"
              />
              <input
                type="number"
                placeholder="Gap (s)"
                value={draft.gap_seconds}
                onChange={(e) => setDraft({ ...draft, gap_seconds: e.target.value })}
                className="px-3 py-2 rounded-xl border border-sand bg-[#FDFBF7] text-sm"
              />
              <input
                type="number"
                placeholder="Max attempts"
                value={draft.max_attempts}
                onChange={(e) => setDraft({ ...draft, max_attempts: e.target.value })}
                className="px-3 py-2 rounded-xl border border-sand bg-[#FDFBF7] text-sm"
              />
            </div>
          </details>
          <button
            type="submit"
            className="w-full py-3 rounded-full bg-[#59745D] hover:bg-[#4A604D] text-white font-medium flex items-center justify-center gap-2"
            data-testid="reminder-create-btn"
          >
            <Plus size={16}/> Set reminder
          </button>
        </form>
      </section>

      {/* List */}
      <section data-testid="reminders-list">
        <h2 className="font-serif text-2xl text-[#2D312E] mb-3">Upcoming</h2>
        {list.length === 0 ? (
          <p className="text-sm text-[#9A9F9D] italic">Nothing on your radar.</p>
        ) : (
          <ul className="space-y-2">
            {list.map((r) => (
              <li key={r.id} className="rounded-2xl bg-white border border-sand p-4 flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-[#2D312E] truncate">{r.title}</p>
                  <p className="text-xs text-[#6B7270] mt-0.5">{new Date(r.fire_at).toLocaleString()}</p>
                  {r.body && <p className="text-xs text-[#9A9F9D] mt-1 line-clamp-2">{r.body}</p>}
                </div>
                <button
                  onClick={() => remove(r.id)}
                  className="text-[#C27A62] p-1.5 rounded-full hover:bg-[#F4F1EA]"
                  data-testid={`reminder-delete-${r.id}`}
                  title="Delete"
                >
                  <Trash2 size={14}/>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C] block mb-1.5">{label}</span>
      {children}
    </label>
  );
}

function Select({ value, onChange, options, disabled, testid }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      data-testid={testid}
      className="w-full px-3 py-2 rounded-xl border border-sand bg-[#FDFBF7] text-sm text-[#2D312E] focus:outline-none focus:border-[#59745D]"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}
