import React from "react";
import { Card, Eyebrow } from "../Layout";
import { Button } from "../ui/button";
import { Compass, Sparkles } from "lucide-react";

const DEFAULT_LABELS = ["GROOMING", "STYLE", "FOCUS", "CONNECT", "GEAR"];

export default function DailyBriefCard({ brief, loading, onGenerate }) {
  return (
    <Card className="md:col-span-3 bg-gradient-to-br from-[#FAF6EC] to-white border-0" data-testid="card-daily-brief">
      <div className="flex items-center gap-2 mb-2">
        <Compass size={18} strokeWidth={1.5} className="text-[#59745D]"/>
        <Eyebrow>Companion's brief</Eyebrow>
      </div>
      {brief ? (
        <div className="mt-3 grid grid-cols-1 md:grid-cols-5 gap-3">
          {brief.split(/\n+/).filter(Boolean).slice(0, 5).map((line, i) => {
            const m = line.match(/^([A-Z][A-Z &]+):\s*(.*)$/);
            const label = m ? m[1] : DEFAULT_LABELS[i] || "";
            const body = m ? m[2] : line;
            return (
              <div key={i} className="bg-white rounded-2xl border border-sand p-4" data-testid={`brief-${i}`}>
                <p className="text-[10px] uppercase tracking-widest text-[#C27A62]">{label}</p>
                <p className="text-sm text-[#2D312E] mt-1 leading-relaxed">{body}</p>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-[#6B7270] mt-2 max-w-2xl leading-relaxed">
          Five tiny suggestions for today — grooming, style, focus, connection, gear — drawn from your profile, plan, and what your companion remembers.
        </p>
      )}
      <Button
        onClick={onGenerate}
        disabled={loading}
        className="mt-5 rounded-full bg-[#59745D] hover:bg-[#4A604D]"
        data-testid="daily-brief-btn"
      >
        <Sparkles size={14} strokeWidth={1.5} className="mr-1"/>
        {loading ? "Listening to your day…" : brief ? "Refresh brief" : "Get today's brief"}
      </Button>
    </Card>
  );
}
