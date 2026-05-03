import React from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { Input } from "../ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { PERSONAS } from "./CompanionSidePanel";

export default function CompanionSettings({ open, onOpenChange, companion, setCompanion, onUpdate }) {
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
        </div>
      </DialogContent>
    </Dialog>
  );
}
