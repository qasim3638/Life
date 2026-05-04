import React, { useEffect, useRef, useState } from "react";
import { Lock } from "lucide-react";
import { api } from "../../lib/api";

const SS_KEY = "yaar_unlocked_at";
const SESSION_MS = 1000 * 60 * 30; // 30 min unlock window

export function isUnlockedRecently() {
  const t = Number(sessionStorage.getItem(SS_KEY) || 0);
  return t && (Date.now() - t) < SESSION_MS;
}

export function markUnlocked() {
  sessionStorage.setItem(SS_KEY, String(Date.now()));
}

export function clearUnlock() {
  sessionStorage.removeItem(SS_KEY);
}

/**
 * PIN gate: shows a 4-8 digit numeric input. On correct PIN, calls onUnlock().
 * Calls /api/companion/pin/verify to validate.
 */
export default function PinGate({ companionName, onUnlock }) {
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    setTimeout(() => inputRef.current?.focus(), 80);
  }, []);

  const submit = async (e) => {
    e?.preventDefault();
    if (!pin || pin.length < 4) {
      setError("PIN is at least 4 digits");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.post("/companion/pin/verify", { pin });
      markUnlocked();
      onUnlock();
    } catch (e) {
      setError(e.response?.status === 401 ? "Incorrect PIN" : "Couldn't verify. Try again.");
      setPin("");
      setTimeout(() => inputRef.current?.focus(), 60);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-6" data-testid="pin-gate">
      <div className="max-w-md w-full text-center">
        <div className="w-16 h-16 rounded-full bg-[#F4F1EA] flex items-center justify-center mx-auto">
          <Lock size={26} strokeWidth={1.4} className="text-[#59745D]"/>
        </div>
        <h2 className="font-serif text-3xl text-[#2D312E] mt-5">Just for you.</h2>
        <p className="text-[#6B7270] mt-2 leading-relaxed">
          Enter your PIN to open your conversation with {companionName}.
        </p>

        <form onSubmit={submit} className="mt-7">
          <input
            ref={inputRef}
            type="password"
            inputMode="numeric"
            pattern="\d*"
            autoComplete="off"
            value={pin}
            maxLength={8}
            onChange={(e) => { setPin(e.target.value.replace(/\D/g, "")); setError(""); }}
            placeholder="• • • •"
            className="w-44 mx-auto block text-center text-3xl tracking-[0.5em] font-serif bg-white border border-sand rounded-2xl py-3 focus:outline-none focus:border-[#59745D]"
            data-testid="pin-input"
          />
          {error && <p className="text-sm text-[#B85C50] mt-3" data-testid="pin-error">{error}</p>}
          <button
            type="submit"
            disabled={busy || pin.length < 4}
            className="mt-5 px-8 h-11 rounded-full bg-[#59745D] hover:bg-[#4a6350] text-white text-sm tracking-wider uppercase disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            data-testid="pin-submit"
          >
            {busy ? "Unlocking…" : "Unlock"}
          </button>
        </form>

        <p className="text-xs text-[#9A9F9D] mt-8 leading-relaxed">
          Your conversations stay private. The PIN is hashed — even on this device the raw PIN is never stored.
        </p>
      </div>
    </div>
  );
}
