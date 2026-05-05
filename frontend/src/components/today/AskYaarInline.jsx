import React, { useState } from "react";
import { api } from "../../lib/api";
import { Sparkles, Send, Check } from "lucide-react";
import { toast } from "sonner";

/**
 * Inline "Ask Yaar" mini-composer — sends a message to /companion/chat, auto-applies
 * any safe actions Yaar proposes, and tells the parent to refresh.
 *
 * @param onApplied called after at least one action was applied; parent reloads data.
 */
export default function AskYaarInline({ placeholder, onApplied, hint, testid = "ask-yaar" }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastReply, setLastReply] = useState("");
  const [lastApplied, setLastApplied] = useState([]);

  const send = async () => {
    const msg = text.trim();
    if (!msg || busy) return;
    setBusy(true);
    setLastReply("");
    setLastApplied([]);
    try {
      const { data } = await api.post("/companion/chat", { message: msg });
      const reply = data.reply;
      const actions = reply?.actions || [];
      const appliedSummaries = [];
      // Auto-apply every proposed action
      for (const a of actions) {
        if (a.status !== "pending") continue;
        try {
          const r = await api.post(`/companion/messages/${reply.id}/actions/${a.id}/apply`);
          appliedSummaries.push(r.data?.action?.result || "Done");
        } catch (e) {
          // soft fail per-action
        }
      }
      setLastReply(reply?.content || "");
      setLastApplied(appliedSummaries);
      setText("");
      if (appliedSummaries.length > 0) {
        toast.success(appliedSummaries.length === 1 ? appliedSummaries[0] : `${appliedSummaries.length} changes applied`);
        onApplied?.();
      } else if (actions.length === 0 && reply?.content) {
        toast.message(reply.content.slice(0, 140));
      }
    } catch (e) {
      toast.error("Yaar couldn't hear that. Try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-5 rounded-2xl border border-[#D8E2D9] bg-[#EDF1ED]/50 p-3" data-testid={testid}>
      <div className="flex items-start gap-2">
        <div className="shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-[#59745D] to-[#A3897C] flex items-center justify-center mt-0.5">
          <Sparkles size={12} strokeWidth={1.5} className="text-white"/>
        </div>
        <div className="flex-1">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); send(); } }}
            placeholder={placeholder || "Ask Yaar to update anything here…"}
            className="w-full bg-transparent border-0 focus:outline-none text-[15px] text-[#2D312E] placeholder:text-[#9A9F9D] py-1"
            data-testid={`${testid}-input`}
            disabled={busy}
          />
          {hint && !text && !lastReply && (
            <p className="text-[11px] text-[#9A9F9D] mt-0.5 italic leading-snug">{hint}</p>
          )}
          {lastApplied.length > 0 && (
            <div className="mt-2 space-y-0.5" data-testid={`${testid}-applied`}>
              {lastApplied.map((s, i) => (
                <p key={i} className="text-xs text-[#59745D] flex items-center gap-1.5">
                  <Check size={12} strokeWidth={2}/> {s}
                </p>
              ))}
            </div>
          )}
          {lastReply && lastApplied.length === 0 && (
            <p className="text-xs text-[#6B7270] mt-2 italic leading-relaxed" data-testid={`${testid}-reply`}>
              {lastReply}
            </p>
          )}
        </div>
        <button
          onClick={send}
          disabled={busy || !text.trim()}
          className="shrink-0 w-9 h-9 rounded-full bg-[#59745D] hover:bg-[#4a6350] text-white flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          title="Send to Yaar (Enter)"
          data-testid={`${testid}-send`}
        >
          <Send size={14} strokeWidth={1.5}/>
        </button>
      </div>
    </div>
  );
}
