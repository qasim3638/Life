import React, { useEffect, useState } from "react";
import { api, API, authStore } from "../lib/api";
import axios from "axios";

/**
 * AuthGate — wraps the whole app. Shows a full-screen lock with a password
 * prompt until a valid JWT is in localStorage. Transparent in dev/preview
 * environments where the backend has no AUTH_EMAIL set (backend returns 200
 * on /auth/me without a token in that case? No — our middleware only enforces
 * if env vars are set. So on dev we just treat any 200 as "authed").
 *
 * Single-user app — email is just a second factor, owner sets it on Railway.
 */
export default function AuthGate({ children }) {
  const [state, setState] = useState("checking"); // checking | authed | locked
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  // Initial probe
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = authStore.getToken();
      if (!token) {
        // No token — but backend might be open (no env vars set). Try anon probe.
        try {
          const res = await axios.get(`${API}/`);
          if (!cancelled && res.status === 200) {
            // If /api/ health says ok AND we can hit an authed endpoint without token,
            // auth is effectively disabled backend-side. But we can't be sure — only
            // /auth/me is the truth. Call it.
            await axios.get(`${API}/auth/me`);
            if (!cancelled) setState("authed");
          }
        } catch {
          if (!cancelled) setState("locked");
        }
        return;
      }
      try {
        await api.get("/auth/me");
        if (!cancelled) setState("authed");
      } catch {
        if (!cancelled) {
          authStore.clear();
          setState("locked");
        }
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

  // locked — lock screen
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
