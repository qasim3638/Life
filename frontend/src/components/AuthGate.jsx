import React, { useEffect, useState } from "react";
import { api, API, authStore } from "../lib/api";
import axios from "axios";

/**
 * AuthGate — wraps the whole app.
 *
 * Flow:
 *   1. GET /api/auth/status to see if a password is set
 *   2. If not configured → app is open, render children directly
 *   3. If configured + valid token in localStorage → render children
 *   4. Else → show lock screen
 */
export default function AuthGate({ children }) {
  const [state, setState] = useState("checking"); // checking | authed | locked
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await axios.get(`${API}/auth/status`);
        if (cancelled) return;
        if (!data?.configured) {
          setState("authed");
          return;
        }
        // configured — validate token if any
        const token = authStore.getToken();
        if (!token) {
          setState("locked");
          if (data.email) setEmail(data.email);
          return;
        }
        try {
          await api.get("/auth/me");
          setState("authed");
        } catch {
          authStore.clear();
          setState("locked");
          if (data.email) setEmail(data.email);
        }
      } catch {
        // Backend unreachable — let the app render so user sees something
        if (!cancelled) setState("authed");
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // React to global auth-expired
  useEffect(() => {
    const onExp = () => setState("locked");
    window.addEventListener("life:auth-expired", onExp);
    return () => window.removeEventListener("life:auth-expired", onExp);
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/auth/login`, {
        email: email.trim().toLowerCase(),
        password,
      });
      authStore.setToken(data.token);
      setState("authed");
      setPassword("");
    } catch (e2) {
      const d = e2?.response?.data?.detail;
      setErr(typeof d === "string" ? d : "Couldn't sign in. Try again.");
    } finally {
      setBusy(false);
    }
  };

  if (state === "checking") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FDFBF7]">
        <div className="text-[#59745D] text-sm tracking-[0.3em] uppercase opacity-70">Life Blueprint</div>
      </div>
    );
  }

  if (state === "authed") return children;

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#FDFBF7] px-6" data-testid="auth-gate">
      <div className="w-full max-w-sm">
        <div className="text-center mb-10">
          <p className="text-[10px] uppercase tracking-[0.4em] text-[#A3897C]">Life</p>
          <h1 className="font-serif text-5xl text-[#2D312E] mt-2">Blueprint</h1>
          <p className="text-sm text-[#6B7270] mt-4">Welcome back. Sign in to continue.</p>
        </div>

        <form onSubmit={submit} className="space-y-4" data-testid="auth-gate-form">
          <div>
            <label className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C]">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="w-full mt-2 px-4 py-3 bg-white border border-[#E5DED3] rounded-2xl text-[#2D312E] focus:outline-none focus:border-[#59745D]"
              data-testid="auth-email-input"
            />
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-[0.3em] text-[#A3897C]">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="w-full mt-2 px-4 py-3 bg-white border border-[#E5DED3] rounded-2xl text-[#2D312E] focus:outline-none focus:border-[#59745D]"
              data-testid="auth-password-input"
            />
          </div>

          {err && (
            <p className="text-sm text-[#C27A62]" data-testid="auth-error">{err}</p>
          )}

          <button
            type="submit"
            disabled={busy || !email || !password}
            className="w-full py-3 rounded-full bg-[#59745D] hover:bg-[#4A604D] text-white font-medium disabled:opacity-50 transition-colors"
            data-testid="auth-submit-btn"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="text-xs text-[#9A9F9D] text-center mt-10 leading-relaxed">
          One life. One honest day at a time.
        </p>
      </div>
    </div>
  );
}
