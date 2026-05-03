import React from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { Button } from "../ui/button";
import { Textarea } from "../ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { Plus, Trash2, Pin } from "lucide-react";

const CATEGORIES = ["general", "family", "work", "health", "dream", "story"];

export default function MemoriesDialog({
  open, onOpenChange, companionName, memories,
  newMem, setNewMem, onAdd, onRemove, onTogglePin,
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-3xl max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="font-serif text-2xl">Things {companionName} remembers</DialogTitle></DialogHeader>
        <div className="space-y-4 mt-2">
          <div className="bg-[#F4F1EA] rounded-2xl p-4">
            <p className="text-xs uppercase tracking-widest text-[#9A9F9D] mb-2">Add a memory</p>
            <Textarea
              value={newMem.content}
              onChange={(e) => setNewMem({ ...newMem, content: e.target.value })}
              placeholder="Tell them something they should always remember…"
              rows={3}
              className="bg-white"
              data-testid="memory-content-input"
            />
            <div className="flex gap-2 mt-3">
              <Select value={newMem.category} onValueChange={(v) => setNewMem({ ...newMem, category: v })}>
                <SelectTrigger className="bg-white" data-testid="memory-category-select"><SelectValue/></SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
              <Button onClick={onAdd} className="rounded-full bg-[#59745D]" data-testid="add-memory-btn">
                <Plus size={14} className="mr-1"/> Save
              </Button>
            </div>
          </div>

          <div>
            <p className="text-xs uppercase tracking-widest text-[#9A9F9D] mb-2">Saved ({memories.length})</p>
            {memories.length === 0 && <p className="text-sm text-[#9A9F9D] italic">Empty.</p>}
            <div className="space-y-2">
              {memories.map(m => (
                <div key={m.id} className="flex items-start gap-3 bg-white border border-sand rounded-2xl px-4 py-3" data-testid={`memory-${m.id}`}>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] uppercase tracking-widest text-[#C27A62]">{m.category}</span>
                      {m.pinned && <Pin size={11} strokeWidth={1.5} className="text-[#59745D] fill-[#59745D]"/>}
                    </div>
                    <p className="text-sm text-[#2D312E] leading-relaxed mt-1">{m.content}</p>
                  </div>
                  <button onClick={() => onTogglePin(m)} className={`shrink-0 ${m.pinned ? "text-[#59745D]" : "text-[#9A9F9D] hover:text-[#59745D]"}`} data-testid={`pin-memory-${m.id}`} title={m.pinned ? "Unpin" : "Pin (never auto-evicted)"}>
                    <Pin size={14} strokeWidth={1.5} className={m.pinned ? "fill-[#59745D]" : ""}/>
                  </button>
                  <button onClick={() => onRemove(m.id)} className="text-[#9A9F9D] hover:text-[#B85C50]"><Trash2 size={14} strokeWidth={1.5}/></button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
