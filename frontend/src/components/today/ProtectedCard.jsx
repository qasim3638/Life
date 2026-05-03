import React from "react";
import { Link } from "react-router-dom";
import { Card, Eyebrow } from "../Layout";
import { Shield, Timer } from "lucide-react";

export default function ProtectedCard({ addictions, focusToday }) {
  if (addictions.length === 0 && focusToday.today_focus_min <= 0) return null;

  const longest = addictions.reduce((max, a) => {
    const ms = Date.now() - new Date(a.started_clean).getTime();
    const days = Math.max(0, Math.floor(ms / 86400000));
    return days > max ? days : max;
  }, 0);

  return (
    <Card className="md:col-span-3" data-testid="card-protected">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2 mb-3">
        <Eyebrow>What you're protecting</Eyebrow>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-[auto_1fr] gap-6 items-start">
        <div className="flex items-baseline gap-x-3 gap-y-1 flex-wrap">
          {addictions.length > 0 && (
            <>
              <Shield size={16} strokeWidth={1.5} className="text-[#59745D]"/>
              <span className="font-serif text-3xl text-[#2D312E]">{longest}</span>
              <span className="text-sm text-[#6B7270]">day{longest === 1 ? "" : "s"} clean</span>
            </>
          )}
          {addictions.length > 0 && focusToday.today_focus_min > 0 && (
            <span className="text-[#9A9F9D] mx-1">·</span>
          )}
          {focusToday.today_focus_min > 0 && (
            <>
              <Timer size={16} strokeWidth={1.5} className="text-[#C27A62]"/>
              <span className="font-serif text-3xl text-[#2D312E]">{focusToday.today_focus_min}</span>
              <span className="text-sm text-[#6B7270]">min focused today</span>
            </>
          )}
        </div>

        {addictions.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {addictions.map(a => {
              const ms = Date.now() - new Date(a.started_clean).getTime();
              const days = Math.max(0, Math.floor(ms / 86400000));
              return (
                <Link key={a.id} to="/sobriety" className="px-4 py-2 rounded-2xl bg-[#F4F1EA] hover:bg-sand transition-colors text-sm" data-testid={`addiction-pill-${a.id}`}>
                  <span className="text-[#2D312E] font-medium">{a.name}</span>
                  <span className="text-[#6B7270]"> · {days}d</span>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </Card>
  );
}
