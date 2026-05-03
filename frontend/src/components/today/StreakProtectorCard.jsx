import React from "react";
import { Link } from "react-router-dom";
import { Card, Eyebrow } from "../Layout";
import { Button } from "../ui/button";
import { Shield, Flame, HeartPulse } from "lucide-react";

export default function StreakProtectorCard({ workoutToday, journalToday }) {
  const messages = [
    !workoutToday && "A five-minute walk still counts. Even one set, even one breath of effort.",
    !journalToday && "A single sentence still counts. One thing you noticed today.",
  ].filter(Boolean);

  return (
    <Card className="md:col-span-3 bg-gradient-to-r from-[#C27A62]/15 via-[#F4F1EA] to-transparent border-0" data-testid="streak-protector">
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-full bg-white border border-sand flex items-center justify-center shrink-0">
          <Shield size={18} strokeWidth={1.5} className="text-[#C27A62]"/>
        </div>
        <div className="flex-1">
          <Eyebrow>Streak protector</Eyebrow>
          <p className="font-serif text-xl md:text-2xl text-[#2D312E] mt-1 leading-snug">
            {messages[0]}
          </p>
          {messages[1] && (
            <p className="text-sm text-[#6B7270] mt-2 leading-relaxed">{messages[1]}</p>
          )}
          <div className="flex flex-wrap gap-2 mt-4">
            {!workoutToday && (
              <Link to="/fitness">
                <Button size="sm" variant="outline" className="rounded-full border-[#59745D] text-[#59745D] hover:bg-[#59745D] hover:text-white" data-testid="protect-workout-btn">
                  <Flame size={13} strokeWidth={1.5} className="mr-1"/> Log a small movement
                </Button>
              </Link>
            )}
            {!journalToday && (
              <Link to="/self-care">
                <Button size="sm" variant="outline" className="rounded-full border-[#C27A62] text-[#C27A62] hover:bg-[#C27A62] hover:text-white" data-testid="protect-journal-btn">
                  <HeartPulse size={13} strokeWidth={1.5} className="mr-1"/> Write one sentence
                </Button>
              </Link>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}
