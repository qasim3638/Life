/**
 * Settings — unified hub for auth, voice, hands-free, whisper mode, etc.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, API, authStore } from "../lib/api";
import axios from "axios";
import {
  Lock, ShieldOff, Volume2, Bell as BellIcon, Mic, ChevronRight, LogOut, Check, AlertCircle, Key,
} from "lucide-react";
import { toast } from "sonner";
import { elevenStore, DEFAULT_VOICE_ID } from "../lib/elevenLabsTTS";

export default function Settings() {
  const [authStatus, setAuthStatus] = useState(null);

  const refresh = async () => {
    try {
      const { data } = await axios.get(`${API}/auth/status`);
      setAuthStatus(data);
    } catch {
      setAuthStatus({ configured: false });
    }
  };

  useEffect(() => { refresh(); }, []);

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 space-y-8" data-testid="settings-page">
      <header>
        <p className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C]">Yaar</p>
        <h1 className="font-serif text-4xl text-[#2D312E] mt-1">Settings</h1>
        <p className="text-sm text-[#6B7270] mt-2 leading-relaxed">
          Manage your account, voice, and how Yaar reaches out to you.
        </p>
      </header>

      <AccountSection authStatus={authStatus} onChanged={refresh}/>

      <ElevenLabsSection/>

      <LinkCard
        to="/voice"
        icon={Volume2}
        title="Voice"
        sub="Pick Yaar's voice — English, Hindi, Urdu samples"
        testid="settings-link-voice"
      />
      <LinkCard
        to="/reminders"
        icon={BellIcon}
        title="Reminders & Whisper Mode"
        sub="Set how Yaar gently summons you for tasks"
        testid="settings-link-reminders"
      />
      <CardSimple
        icon={Mic}
        title="Hands-free (Hi Yaar)"
        sub="Tap the gear icon near the mic, bottom right of any page"
      />
    </div>
  );
}

function ElevenLabsSection() {
  const [apiKey, setApiKey] = useState("");
  const [voiceId, setVoiceId] = useState("");
  const [hasKey, setHasKey] = useState(false);
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    setApiKey(elevenStore.getKey());
    setVoiceId(elevenStore.getVoiceId());
    setHasKey(elevenStore.hasKey());
  }, []);

  const save = () => {
    elevenStore.setKey(apiKey);
    elevenStore.setVoiceId(voiceId || DEFAULT_VOICE_ID);
    setHasKey(elevenStore.hasKey());
    toast.success("ElevenLabs settings saved. Yaar will use this voice now.");
  };

  const remove = () => {
    elevenStore.setKey("");
    setApiKey("");
    setHasKey(false);
    toast.message("ElevenLabs key removed. Yaar falls back to OpenAI voice.");
  };

  return (
    <section className="rounded-2xl bg-white border border-sand p-6" data-testid="settings-eleven">
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-full bg-[#C27A62]/10 flex items-center justify-center text-[#C27A62] shrink-0">
          <Key size={18} strokeWidth={1.5}/>
        </div>
        <div className="flex-1">
          <p className="font-medium text-[#2D312E]">ElevenLabs voice (premium)</p>
          <p className="text-xs text-[#6B7270] mt-1 leading-relaxed">
            Paste your ElevenLabs API key for a much warmer, multilingual voice (English/Hindi/Urdu).
            Stored only on this device. {hasKey ? <span className="text-[#59745D]">· Connected</span> : <span className="text-[#A3897C]">· Not set</span>}
          </p>

          <div className="mt-4 space-y-3">
            <div>
              <label className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C]">API Key</label>
              <div className="flex gap-2 mt-1">
                <input
                  type={showKey ? "text" : "password"}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk_..."
                  className="flex-1 px-3 py-2 bg-[#F4F1EA] rounded-xl text-sm text-[#2D312E] focus:outline-none focus:ring-2 focus:ring-[#59745D]"
                  data-testid="eleven-key-input"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(s => !s)}
                  className="px-3 py-2 bg-[#F4F1EA] rounded-xl text-xs text-[#6B7270] hover:bg-[#E9E4D8]"
                >
                  {showKey ? "Hide" : "Show"}
                </button>
              </div>
            </div>

            <div>
              <label className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C]">Voice ID (optional)</label>
              <input
                type="text"
                value={voiceId}
                onChange={(e) => setVoiceId(e.target.value)}
                placeholder={DEFAULT_VOICE_ID + " (Adam)"}
                className="w-full mt-1 px-3 py-2 bg-[#F4F1EA] rounded-xl text-sm text-[#2D312E] focus:outline-none focus:ring-2 focus:ring-[#59745D] font-mono"
                data-testid="eleven-voice-input"
              />
              <p className="text-[10px] text-[#9A9F9D] mt-1">
                Find voice IDs at elevenlabs.io → Voices → click your voice → copy ID. Leave blank for Adam.
              </p>
            </div>

            <div className="flex gap-2">
              <button
                onClick={save}
                disabled={!apiKey.trim()}
                className="flex-1 py-2 rounded-full bg-[#59745D] hover:bg-[#4A604D] text-white text-sm font-medium disabled:opacity-50"
                data-testid="eleven-save-btn"
              >
                Save
              </button>
              {hasKey && (
                <button
                  onClick={remove}
                  className="px-4 py-2 rounded-full border border-sand text-[#B85C50] text-sm hover:bg-[#FBF5F2]"
                  data-testid="eleven-remove-btn"
                >
                  Remove
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function LinkCard({ to, icon: Icon, title, sub, testid }) {
  return (
    <Link
      to={to}
      data-testid={testid}
      className="flex items-center gap-4 rounded-2xl bg-white border border-sand p-5 hover:bg-[#F4F1EA] transition-colors"
    >
      <div className="w-10 h-10 rounded-full bg-[#59745D]/10 flex items-center justify-center text-[#59745D]">
        <Icon size={18} strokeWidth={1.5}/>
      </div>
      <div className="flex-1">
        <p className="font-medium text-[#2D312E]">{title}</p>
        <p className="text-xs text-[#6B7270] mt-0.5">{sub}</p>
      </div>
      <ChevronRight size={16} className="text-[#9A9F9D]"/>
    </Link>
  );
}

function CardSimple({ icon: Icon, title, sub }) {
  return (
    <div className="flex items-center gap-4 rounded-2xl bg-white border border-sand p-5">
      <div className="w-10 h-10 rounded-full bg-[#59745D]/10 flex items-center justify-center text-[#59745D]">
        <Icon size={18} strokeWidth={1.5}/>
      </div>
      <div className="flex-1">
        <p className="font-medium text-[#2D312E]">{title}</p>
        <p className="text-xs text-[#6B7270] mt-0.5">{sub}</p>
      </div>
    </div>
  );
}

function AccountSection({ authStatus, onChanged }) {
  const [mode, setMode] = useState("idle"); // idle | setup | change | disable
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [current, setCurrent] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (authStatus?.email) setEmail(authStatus.email);
  }, [authStatus]);

  if (!authStatus) {
    return (
      <div className="rounded-2xl bg-white border border-sand p-5 text-sm text-[#9A9F9D]">Loading account…</div>
    );
  }

  const reset = () => {
    setMode("idle"); setPassword(""); setConfirm(""); setCurrent(""); setErr("");
  };

  const submitSetup = async (e) => {
    e.preventDefault();
    setErr("");
    if (password !== confirm) { setErr("Passwords don't match."); return; }
    setBusy(true);
    try {
      const body = { email: email.trim().toLowerCase(), password };
      if (authStatus.configured) body.current_password = current;
      const { data } = await axios.post(`${API}/auth/setup`, body);
      authStore.setToken(data.token);
      toast.success(authStatus.configured ? "Password updated" : "Lock activated");
      reset();
      onChanged?.();
    } catch (e2) {
      setErr(e2?.response?.data?.detail || "Couldn't save");
    } finally {
      setBusy(false);
    }
  };

  const submitDisable = async (e) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      await axios.post(`${API}/auth/disable`, { current_password: current });
      authStore.clear();
      toast.success("Lock screen disabled");
      reset();
      onChanged?.();
    } catch (e2) {
      setErr(e2?.response?.data?.detail || "Couldn't disable");
    } finally {
      setBusy(false);
    }
  };

  const signOut = () => {
    authStore.clear();
    toast.message("Signed out");
    window.location.reload();
  };

  return (
    <div className="rounded-2xl bg-white border border-sand p-5 space-y-4" data-testid="settings-account">
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-full bg-[#59745D]/10 flex items-center justify-center text-[#59745D]">
          {authStatus.configured ? <Lock size={18} strokeWidth={1.5}/> : <ShieldOff size={18} strokeWidth={1.5}/>}
        </div>
        <div className="flex-1">
          <p className="font-medium text-[#2D312E] flex items-center gap-2">
            Account & Lock Screen
            {authStatus.configured ? <Check size={14} className="text-[#59745D]"/> : <AlertCircle size={14} className="text-[#C27A62]"/>}
          </p>
          <p className="text-xs text-[#6B7270] mt-0.5">
            {authStatus.configured
              ? `Locked with ${authStatus.email || "your password"}.`
              : "App is currently OPEN — anyone with the URL can see it."}
          </p>
        </div>
      </div>

      {mode === "idle" && (
        <div className="flex flex-wrap gap-2 pt-1">
          {!authStatus.configured && (
            <button
              onClick={() => setMode("setup")}
              className="px-4 py-2 rounded-full bg-[#59745D] hover:bg-[#4A604D] text-white text-sm font-medium"
              data-testid="settings-setup-password-btn"
            >
              Set up password
            </button>
          )}
          {authStatus.configured && (
            <>
              <button
                onClick={() => setMode("change")}
                className="px-4 py-2 rounded-full bg-[#59745D] hover:bg-[#4A604D] text-white text-sm font-medium"
                data-testid="settings-change-password-btn"
              >
                Change password
              </button>
              <button
                onClick={() => setMode("disable")}
                className="px-4 py-2 rounded-full bg-white border border-sand text-[#C27A62] text-sm"
                data-testid="settings-disable-btn"
              >
                Turn lock off
              </button>
              <button
                onClick={signOut}
                className="px-4 py-2 rounded-full bg-white border border-sand text-[#6B7270] text-sm flex items-center gap-1"
                data-testid="settings-signout-btn"
              >
                <LogOut size={13}/> Sign out
              </button>
            </>
          )}
        </div>
      )}

      {(mode === "setup" || mode === "change") && (
        <form onSubmit={submitSetup} className="space-y-3 pt-2" data-testid="settings-setup-form">
          {mode === "change" && (
            <Field label="Current password">
              <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)}
                required className={inp} autoComplete="current-password"
                data-testid="settings-current-password"/>
            </Field>
          )}
          <Field label="Email">
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              required className={inp} autoComplete="email"
              data-testid="settings-email-input"/>
          </Field>
          <Field label={mode === "change" ? "New password" : "Password"}>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              required minLength={4} className={inp} autoComplete="new-password"
              data-testid="settings-new-password"/>
          </Field>
          <Field label="Confirm">
            <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
              required minLength={4} className={inp} autoComplete="new-password"
              data-testid="settings-confirm-password"/>
          </Field>
          {err && <p className="text-xs text-[#C27A62]" data-testid="settings-err">{err}</p>}
          <div className="flex gap-2">
            <button type="submit" disabled={busy}
              className="flex-1 py-2.5 rounded-full bg-[#59745D] hover:bg-[#4A604D] text-white text-sm font-medium disabled:opacity-50"
              data-testid="settings-save-btn">
              {busy ? "Saving…" : "Save"}
            </button>
            <button type="button" onClick={reset}
              className="px-4 py-2.5 rounded-full bg-white border border-sand text-[#6B7270] text-sm">
              Cancel
            </button>
          </div>
        </form>
      )}

      {mode === "disable" && (
        <form onSubmit={submitDisable} className="space-y-3 pt-2" data-testid="settings-disable-form">
          <p className="text-xs text-[#C27A62]">
            This wipes your password and turns the lock screen off. Anyone with the URL can open the app.
          </p>
          <Field label="Current password">
            <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)}
              required className={inp} autoComplete="current-password"
              data-testid="settings-disable-current"/>
          </Field>
          {err && <p className="text-xs text-[#C27A62]">{err}</p>}
          <div className="flex gap-2">
            <button type="submit" disabled={busy}
              className="flex-1 py-2.5 rounded-full bg-[#C27A62] hover:bg-[#A65F4A] text-white text-sm font-medium disabled:opacity-50"
              data-testid="settings-disable-confirm">
              {busy ? "…" : "Yes, turn off"}
            </button>
            <button type="button" onClick={reset}
              className="px-4 py-2.5 rounded-full bg-white border border-sand text-[#6B7270] text-sm">
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

const inp = "w-full mt-1 px-3 py-2 rounded-xl border border-sand bg-[#FDFBF7] text-sm text-[#2D312E] focus:outline-none focus:border-[#59745D]";

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C] block">{label}</span>
      {children}
    </label>
  );
}
