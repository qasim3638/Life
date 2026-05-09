import React, { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import { Switch } from "../ui/switch";
import { Sun, CloudSun, Moon, Plus, Trash2, Volume2, Bell } from "lucide-react";
import { toast } from "sonner";
import { loadBriefs, saveBriefs, newCustomBrief } from "../../lib/briefs";
import { syncBriefsToNative, requestNativePermission, isNative } from "../../lib/nativeBridge";
import { api, API, authStore } from "../../lib/api";

const KIND_META = {
  morning: { Icon: Sun, color: "#E5A85C", label: "Morning brief", desc: "Priorities, events, weather, gentle nudges to start the day" },
  midday: { Icon: CloudSun, color: "#C27A62", label: "Midday check-in", desc: "Quick pulse — what's still on the list, half the day to go" },
  evening: { Icon: Moon, color: "#59745D", label: "Evening wind-down", desc: "What got done, mood check, tomorrow's first move" },
  custom: { Icon: Bell, color: "#A3897C", label: "Custom brief", desc: "Anything you want — set the time and the prompt" },
};

export default function BriefSettingsDialog({ open, onOpenChange }) {
  const [briefs, setBriefs] = useState([]);
  const [notifPerm, setNotifPerm] = useState(typeof Notification !== "undefined" ? Notification.permission : "unsupported");
  const [previewBusy, setPreviewBusy] = useState(null);

  useEffect(() => {
    if (open) setBriefs(loadBriefs());
  }, [open]);

  const update = (id, patch) => {
    const next = briefs.map(b => b.id === id ? { ...b, ...patch } : b);
    setBriefs(next); saveBriefs(next);
    syncBriefsToNative(next);
  };

  const remove = (id) => {
    if (!window.confirm("Remove this brief?")) return;
    const next = briefs.filter(b => b.id !== id);
    setBriefs(next); saveBriefs(next);
    syncBriefsToNative(next);
  };

  const addCustom = () => {
    const next = [...briefs, newCustomBrief()];
    setBriefs(next); saveBriefs(next);
    syncBriefsToNative(next);
  };

  const askPerm = async () => {
    if (isNative()) {
      const r = await requestNativePermission();
      if (r === "granted") {
        toast.success("Notifications enabled on your phone");
        setNotifPerm("granted");
        syncBriefsToNative(loadBriefs());
      } else {
        toast.error("Allow Life Blueprint to send notifications in phone Settings");
      }
      return;
    }
    if (typeof Notification === "undefined") return;
    try {
      const r = await Notification.requestPermission();
      setNotifPerm(r);
      if (r === "granted") toast.success("Notifications enabled");
      else if (r === "denied") toast.error("Notifications blocked. Allow them in browser settings.");
    } catch {}
  };

  const preview = async (b) => {
    setPreviewBusy(b.id);
    try {
      const body = b.kind === "custom" ? { kind: "custom", custom_prompt: b.prompt || "" } : { kind: b.kind };
      const { data } = await api.post("/voice/brief", body);
      const text = data?.text || "";
      if (!text) { toast.error("Couldn't build a brief — check your data"); return; }
      // Speak it
      const token = authStore.getToken();
      const res = await fetch(`${API}/voice/speak`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ text: text.slice(0, 4000), voice: "coral", provider: "openai" }),
      });
      if (!res.ok) { toast.error("Couldn't generate audio"); return; }
      const blob = await res.blob();
      const audio = new Audio(URL.createObjectURL(blob));
      try { await audio.play(); } catch {}
      toast.message(text.slice(0, 200));
    } catch (e) {
      toast.error("Preview failed");
    } finally {
      setPreviewBusy(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-3xl max-w-2xl max-h-[88vh] overflow-hidden flex flex-col p-0">
        <DialogHeader className="px-6 pt-6 pb-3 border-b border-sand">
          <DialogTitle className="font-serif text-2xl text-[#2D312E]">Voice briefs</DialogTitle>
          <p className="text-sm text-[#6B7270] mt-1 leading-relaxed">
            Yaar will speak a short summary at the times you choose. If you're on the app it auto-plays;
            otherwise you'll get a notification.
          </p>
        </DialogHeader>

        <div className="px-6 py-4 space-y-3 overflow-y-auto" data-testid="brief-settings-body">
          {/* Notification permission */}
          <div className="rounded-2xl border border-sand bg-[#FDFBF7] px-4 py-3 flex items-center gap-3">
            <Bell size={16} strokeWidth={1.5} className="text-[#59745D]"/>
            <div className="flex-1">
              <p className="text-sm text-[#2D312E] font-medium">
                {isNative() ? "Phone notifications" : "Browser notifications"}
              </p>
              <p className="text-xs text-[#6B7270]">
                {isNative() && notifPerm !== "granted" && "Off — turn on so Yaar reaches you when the app is closed."}
                {isNative() && notifPerm === "granted" && "Enabled — Yaar will ping you on your lock screen at brief time."}
                {!isNative() && notifPerm === "granted" && "Enabled — Yaar will ping you when the app is closed."}
                {!isNative() && notifPerm === "denied" && "Blocked. Allow them in your browser site settings."}
                {!isNative() && notifPerm === "default" && "Off — turn on so Yaar can reach you when you're not on the app."}
                {!isNative() && notifPerm === "unsupported" && "Not supported on this browser."}
              </p>
            </div>
            {(notifPerm === "default" || (isNative() && notifPerm !== "granted")) && (
              <Button size="sm" className="rounded-full bg-[#59745D] hover:bg-[#4a6350]" onClick={askPerm} data-testid="brief-notif-enable">
                Enable
              </Button>
            )}
          </div>

          {briefs.map(b => {
            const meta = KIND_META[b.kind] || KIND_META.custom;
            const Icon = meta.Icon;
            return (
              <div
                key={b.id}
                className={`rounded-2xl border bg-white px-4 py-3 ${b.enabled ? "border-[#D8E2D9]" : "border-sand opacity-70"}`}
                data-testid={`brief-row-${b.id}`}
              >
                <div className="flex items-start gap-3">
                  <span className="w-9 h-9 rounded-full flex items-center justify-center shrink-0 mt-0.5" style={{ background: `${meta.color}22` }}>
                    <Icon size={16} strokeWidth={1.5} style={{ color: meta.color }}/>
                  </span>
                  <div className="flex-1 min-w-0">
                    {b.kind === "custom" ? (
                      <Input
                        value={b.label}
                        onChange={(e) => update(b.id, { label: e.target.value.slice(0, 40) })}
                        placeholder="What do you want to call this?"
                        className="bg-transparent border-0 border-b border-sand rounded-none px-0 h-7 text-[15px] font-medium focus:border-[#59745D] focus-visible:ring-0"
                        data-testid={`brief-label-${b.id}`}
                      />
                    ) : (
                      <p className="text-[15px] font-medium text-[#2D312E]">{meta.label}</p>
                    )}
                    <p className="text-xs text-[#6B7270] mt-0.5 leading-relaxed">{meta.desc}</p>
                    {b.kind === "custom" && (
                      <textarea
                        value={b.prompt || ""}
                        onChange={(e) => update(b.id, { prompt: e.target.value.slice(0, 400) })}
                        placeholder="Tell Yaar what to say. e.g. 'Read me my top priority and remind me to drink water.'"
                        className="w-full mt-2 bg-[#FDFBF7] border border-sand rounded-xl p-2 text-sm text-[#2D312E] focus:outline-none focus:border-[#59745D] resize-none"
                        rows={2}
                        data-testid={`brief-prompt-${b.id}`}
                      />
                    )}
                    <div className="flex items-center gap-2 mt-2">
                      <Input
                        type="time"
                        value={b.time}
                        onChange={(e) => update(b.id, { time: e.target.value })}
                        className="w-28 h-9 rounded-full bg-[#FDFBF7] border-sand"
                        data-testid={`brief-time-${b.id}`}
                      />
                      <button
                        onClick={() => preview(b)}
                        disabled={previewBusy === b.id}
                        className="text-xs text-[#59745D] hover:underline underline-offset-4 inline-flex items-center gap-1 disabled:opacity-50"
                        data-testid={`brief-preview-${b.id}`}
                      >
                        <Volume2 size={12} strokeWidth={1.5}/> {previewBusy === b.id ? "Generating…" : "Preview"}
                      </button>
                      {b.kind === "custom" && (
                        <button
                          onClick={() => remove(b.id)}
                          className="ml-auto text-xs text-[#B85C50] hover:underline inline-flex items-center gap-1"
                          data-testid={`brief-delete-${b.id}`}
                        >
                          <Trash2 size={12} strokeWidth={1.5}/> Remove
                        </button>
                      )}
                    </div>
                  </div>
                  <Switch
                    checked={b.enabled}
                    onCheckedChange={(v) => update(b.id, { enabled: !!v })}
                    data-testid={`brief-toggle-${b.id}`}
                  />
                </div>
              </div>
            );
          })}

          <button
            onClick={addCustom}
            className="w-full rounded-2xl border-2 border-dashed border-sand text-[#6B7270] py-3 hover:bg-[#FDFBF7] hover:border-[#59745D] hover:text-[#59745D] transition-colors flex items-center justify-center gap-2 text-sm"
            data-testid="brief-add-custom"
          >
            <Plus size={14} strokeWidth={1.5}/> Add custom brief
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
