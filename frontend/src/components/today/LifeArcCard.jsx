import React from "react";
import { Link } from "react-router-dom";
import { Card, Eyebrow } from "../Layout";
import { Button } from "../ui/button";

function ProgressRing({ percent }) {
  const r = 70;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - percent / 100);
  return (
    <svg width="170" height="170" viewBox="0 0 170 170" className="rotate-[-90deg]">
      <circle cx="85" cy="85" r={r} stroke="#E8E2D2" strokeWidth="10" fill="none" />
      <circle
        cx="85" cy="85" r={r}
        stroke="#59745D" strokeWidth="10" fill="none"
        strokeLinecap="round" strokeDasharray={c} strokeDashoffset={offset}
        style={{ transition: "stroke-dashoffset 1.2s ease-out" }}
      />
    </svg>
  );
}

export default function LifeArcCard({ ageNow = 40, targetAge = 80 }) {
  const yearsLeft = targetAge - ageNow;
  const pct = Math.round((ageNow / targetAge) * 100);

  return (
    <Card className="md:col-span-1 flex flex-col items-center text-center" data-testid="card-life-progress">
      <Eyebrow>Your life arc</Eyebrow>
      <div className="relative">
        <ProgressRing percent={pct} />
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <p className="font-serif text-4xl text-[#2D312E]">{yearsLeft}</p>
          <p className="text-xs uppercase tracking-widest text-[#9A9F9D] mt-1">years ahead</p>
        </div>
      </div>
      <p className="text-sm text-[#6B7270] mt-5 leading-relaxed">
        You've lived {ageNow} beautiful years. {yearsLeft} more to shape.
      </p>
      <Link to="/blueprint">
        <Button
          variant="outline"
          className="mt-4 rounded-full border-[#59745D] text-[#59745D] hover:bg-[#59745D] hover:text-white"
          data-testid="view-blueprint-btn"
        >
          View the blueprint
        </Button>
      </Link>
    </Card>
  );
}
