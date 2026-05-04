import React, { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { MapPin, Check, Lock, ShieldOff } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { PERSONAS } from "./CompanionSidePanel";
import { markUnlocked } from "./PinGate";

export default function CompanionSettings({ open, onOpenChange, companion, setCompanion, onUpdate, pinEnabled, setPinEnabled }) {
  const [cityInput, setCityInput] = useState(companion.location_name || "");
  const [saving, setSaving] = useState(false);
  const [pinMode, setPinMode] = useState(null); // null | "set" | "change" | "remove"
  const [newPin, setNewPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [currentPin, setCurrentPin] = useState("");
  const [pinBusy, setPinBusy] = useState(false);

  const closePinForm = () => { setPinMode(null); setNewPin(""); setConfirmPin(""); setCurrentPin(""); };

  const submitPin = async () => {
    if (pinMode === "remove") {
      if (currentPin.length < 4) return toast.error("Enter your current PIN");
      setPinBusy(true);
      try {
        await api.delete("/companion/pin", { data: { current_pin: currentPin } });
        setPinEnabled?.(false);
        toast.success("PIN removed");
        closePinForm();
      } catch (e) {
        toast.error(e.response?.data?.detail || "Couldn't remove PIN");
      } finally { setPinBusy(false); }
      return;
    }
    if (!/^\d{4,8}$/.test(newPin)) return toast.error("PIN must be 4-8 digits");
    if (newPin !== confirmPin) return toast.error("PINs don't match");
    if (pinMode === "change" && currentPin.length < 4) return toast.error("Enter your current PIN");
    setPinBusy(true);
    try {
      const body = { pin: newPin };
      if (pinMode === "change") body.current_pin = currentPin;
      await api.post("/companion/pin", body);
      setPinEnabled?.(true);
      markUnlocked();
      toast.success(pinMode === "change" ? "PIN updated" : "PIN set");
      closePinForm();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Couldn't save PIN");
    } finally { setPinBusy(false); }
  };

  const saveLocation = async () => {
    const q = cityInput.trim();
    if (!q) return toast.error("Type a city name");
    setSaving(true);
    try {
      const { data } = await api.post("/companion/location", { query: q });
      setCompanion(data);
      setCityInput(data.location_name || "");
      toast.success(`Location set to ${data.location_name}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Couldn't find that city — try a larger nearby one");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-3xl">
        <DialogHeader><DialogTitle className="font-serif text-2xl">Companion settings</DialogTitle></DialogHeader>
        <div className="space-y-4 mt-2">
          <div>
            <p className="text-xs uppercase tracking-wider text-[#9A9F9D] mb-1">Their name</p>
            <Input
              value={companion.name}
              onChange={(e) => setCompanion({ ...companion, name: e.target.value })}
              onBlur={(e) => onUpdate({ name: e.target.value })}
              data-testid="settings-name"
            />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider text-[#9A9F9D] mb-1">What they call you</p>
            <Input
              value={companion.user_name}
              onChange={(e) => setCompanion({ ...companion, user_name: e.target.value })}
              onBlur={(e) => onUpdate({ user_name: e.target.value })}
              data-testid="settings-user-name"
            />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider text-[#9A9F9D] mb-1">Persona</p>
            <Select value={companion.persona} onValueChange={(v) => onUpdate({ persona: v })}>
              <SelectTrigger data-testid="settings-persona"><SelectValue/></SelectTrigger>
              <SelectContent>
                {PERSONAS.map(p => <SelectItem key={p.key} value={p.key}>{p.label} — {p.desc}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="border-t border-sand pt-4">
            <p className="text-xs uppercase tracking-wider text-[#9A9F9D] mb-1 flex items-center gap-1">
              <MapPin size={12} strokeWidth={1.5}/> Your city (for live weather)
            </p>
            <div className="flex gap-2">
              <Input
                value={cityInput}
                onChange={(e) => setCityInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") saveLocation(); }}
                placeholder="e.g. Gravesend, London, Dubai"
                data-testid="settings-city-input"
              />
              <Button
                onClick={saveLocation}
                disabled={saving}
                className="rounded-full bg-[#59745D] hover:bg-[#4A604D] shrink-0"
                data-testid="settings-city-save"
              >
                <Check size={14} strokeWidth={1.5} className="mr-1"/>
                {saving ? "Finding…" : "Save"}
              </Button>
            </div>
            {companion.latitude != null && (
              <p className="text-[11px] text-[#9A9F9D] mt-1.5">
                Currently using: {companion.location_name} ({companion.latitude.toFixed(2)}, {companion.longitude.toFixed(2)})
              </p>
            )}
          </div>

          {/* PIN protection */}
          <div className="border-t border-sand pt-4" data-testid="settings-pin-section">
            <p className="text-xs uppercase tracking-wider text-[#9A9F9D] mb-1 flex items-center gap-1">
              <Lock size={12} strokeWidth={1.5}/> Privacy
            </p>
            {!pinMode && (
              <div className="flex items-center justify-between gap-3 bg-[#FDFBF7] rounded-2xl px-4 py-3">
                <div className="text-sm">
                  <p className="text-[#2D312E] font-medium">PIN protection</p>
                  <p className="text-[#6B7270] text-xs mt-0.5">
                    {pinEnabled
                      ? `On — ${companion.name} requires your PIN to open this conversation.`
                      : "Off — anyone on this device can read your chat with your companion."}
                  </p>
                </div>
                {pinEnabled ? (
                  <div className="flex gap-2">
                    <Button size="sm" variant="ghost" className="rounded-full text-[#59745D]" onClick={() => setPinMode("change")} data-testid="pin-change-btn">Change</Button>
                    <Button size="sm" variant="ghost" className="rounded-full text-[#B85C50] hover:text-[#B85C50]" onClick={() => setPinMode("remove")} data-testid="pin-remove-btn">
                      <ShieldOff size={13} strokeWidth={1.5} className="mr-1"/> Remove
                    </Button>
                  </div>
                ) : (
                  <Button size="sm" className="rounded-full bg-[#59745D] hover:bg-[#4a6350]" onClick={() => setPinMode("set")} data-testid="pin-set-btn">Set PIN</Button>
                )}
              </div>
            )}

            {pinMode && (
              <div className="bg-[#FDFBF7] rounded-2xl p-4 space-y-3">
                <p className="text-sm text-[#2D312E] font-medium">
                  {pinMode === "set" && "Set a new PIN"}
                  {pinMode === "change" && "Change your PIN"}
                  {pinMode === "remove" && "Remove PIN protection"}
                </p>

                {(pinMode === "change" || pinMode === "remove") && (
                  <Input
                    type="password" inputMode="numeric" maxLength={8}
                    value={currentPin}
                    onChange={(e) => setCurrentPin(e.target.value.replace(/\D/g, ""))}
                    placeholder="Current PIN"
                    className="bg-white"
                    data-testid="pin-current-input"
                  />
                )}
                {pinMode !== "remove" && (
                  <>
                    <Input
                      type="password" inputMode="numeric" maxLength={8}
                      value={newPin}
                      onChange={(e) => setNewPin(e.target.value.replace(/\D/g, ""))}
                      placeholder="New PIN (4-8 digits)"
                      className="bg-white"
                      data-testid="pin-new-input"
                    />
                    <Input
                      type="password" inputMode="numeric" maxLength={8}
                      value={confirmPin}
                      onChange={(e) => setConfirmPin(e.target.value.replace(/\D/g, ""))}
                      placeholder="Confirm new PIN"
                      className="bg-white"
                      data-testid="pin-confirm-input"
                    />
                  </>
                )}
                <div className="flex justify-end gap-2 pt-1">
                  <Button size="sm" variant="ghost" className="rounded-full text-[#6B7270]" onClick={closePinForm}>Cancel</Button>
                  <Button
                    size="sm"
                    className={`rounded-full ${pinMode === "remove" ? "bg-[#B85C50] hover:bg-[#a14b41]" : "bg-[#59745D] hover:bg-[#4a6350]"}`}
                    disabled={pinBusy}
                    onClick={submitPin}
                    data-testid="pin-submit-btn"
                  >
                    {pinBusy ? "Saving…" : pinMode === "remove" ? "Remove" : "Save PIN"}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
