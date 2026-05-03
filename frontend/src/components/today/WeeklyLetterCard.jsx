import React from "react";
import { Card, Eyebrow } from "../Layout";
import { Button } from "../ui/button";
import { Mail } from "lucide-react";

export default function WeeklyLetterCard({ letter, loading, onGenerate }) {
  return (
    <Card className="md:col-span-3 bg-gradient-to-br from-[#F4F1EA] to-white border-0" data-testid="card-weekly-letter">
      <div className="flex items-center gap-2 mb-2">
        <Mail size={18} strokeWidth={1.5} className="text-[#A3897C]" />
        <Eyebrow>Weekly letter</Eyebrow>
      </div>
      {letter ? (
        <p className="font-serif text-lg md:text-xl text-[#2D312E] mt-3 leading-relaxed whitespace-pre-wrap max-w-3xl">
          {letter}
        </p>
      ) : (
        <p className="text-[#6B7270] mt-2 max-w-2xl leading-relaxed">
          A tender letter to your future self — written from the past seven days of your movement, moods, and moments.
        </p>
      )}
      <Button
        onClick={onGenerate}
        disabled={loading}
        variant="outline"
        className="mt-5 rounded-full border-[#A3897C] text-[#A3897C] hover:bg-[#A3897C] hover:text-white"
        data-testid="weekly-letter-btn"
      >
        <Mail size={14} className="mr-1" strokeWidth={1.5} />
        {loading ? "Writing…" : letter ? "Write another" : "Write this week's letter"}
      </Button>
    </Card>
  );
}
