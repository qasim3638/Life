import React, { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { MapPin, Check } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { PERSONAS } from "./CompanionSidePanel";

export default function CompanionSettings({ open, onOpenChange, companion, setCompanion, onUpdate }) {
  const [cityInput, setCityInput] = useState(companion.location_name || "");
  const [saving, setSaving] = useState(false);

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
        </div>
      </DialogContent>
    </Dialog>
  );
}
