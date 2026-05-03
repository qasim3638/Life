import React from "react";
import { Card, Eyebrow } from "../Layout";
import { Button } from "../ui/button";
import { BookOpen } from "lucide-react";

export const PERSONAS = [
  { key: "friend", label: "Friend", desc: "Warm, present, curious" },
  { key: "secretary", label: "Secretary", desc: "Organised & efficient" },
  { key: "manager", label: "Manager", desc: "Direct & accountable" },
  { key: "coach", label: "Coach", desc: "Reflective & growth-minded" },
];

export default function CompanionSidePanel({ companion, memories, onPersonaChange, onOpenMemories }) {
  return (
    <div className="hidden lg:flex flex-col gap-4">
      <Card>
        <Eyebrow>Mode</Eyebrow>
        <p className="font-serif text-xl text-[#2D312E] mt-1 mb-3">How should {companion.name} show up?</p>
        <div className="space-y-2">
          {PERSONAS.map(p => (
            <button
              key={p.key}
              onClick={() => onPersonaChange(p.key)}
              className={`w-full text-left px-4 py-3 rounded-2xl transition-colors ${
                companion.persona === p.key
                  ? "bg-[#59745D] text-white"
                  : "bg-[#F4F1EA] text-[#2D312E] hover:bg-sand"
              }`}
              data-testid={`persona-${p.key}`}
            >
              <p className="font-medium">{p.label}</p>
              <p className={`text-xs mt-0.5 ${companion.persona === p.key ? "text-white/80" : "text-[#6B7270]"}`}>
                {p.desc}
              </p>
            </button>
          ))}
        </div>
      </Card>
      <Card>
        <Eyebrow>Recent memories</Eyebrow>
        {memories.length === 0 ? (
          <p className="text-sm text-[#9A9F9D] mt-2 italic">Nothing saved yet. Use the star on your messages or add manually.</p>
        ) : (
          <ul className="mt-3 space-y-2 max-h-64 overflow-y-auto">
            {memories.slice(0, 6).map(m => (
              <li key={m.id} className="text-sm text-[#2D312E] bg-[#F4F1EA] rounded-xl px-3 py-2">
                <span className="text-[10px] uppercase tracking-widest text-[#C27A62] block">{m.category}</span>
                {m.content}
              </li>
            ))}
          </ul>
        )}
        <Button variant="ghost" onClick={onOpenMemories} className="rounded-full text-[#59745D] mt-3 w-full" data-testid="manage-memories-btn">
          <BookOpen size={14} strokeWidth={1.5} className="mr-1"/> Manage memories
        </Button>
      </Card>
    </div>
  );
}
