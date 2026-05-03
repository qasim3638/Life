import React from "react";
import { NavLink } from "react-router-dom";
import { Home, Dumbbell, UtensilsCrossed, Sparkles, Brain, Heart, CalendarDays, Compass } from "lucide-react";

const items = [
  { to: "/", label: "Today", icon: Home },
  { to: "/blueprint", label: "Plan", icon: Compass },
  { to: "/fitness", label: "Move", icon: Dumbbell },
  { to: "/recipes", label: "Eat", icon: UtensilsCrossed },
  { to: "/motivation", label: "Wisdom", icon: Sparkles },
  { to: "/meditate", label: "Breathe", icon: Brain },
  { to: "/self-care", label: "Heart", icon: Heart },
  { to: "/events", label: "Dates", icon: CalendarDays },
];

export default function MobileNav() {
  return (
    <nav
      className="lg:hidden fixed bottom-0 inset-x-0 z-50 glass border-t border-sand px-2 py-2 flex items-center justify-between overflow-x-auto"
      data-testid="mobile-nav"
    >
      {items.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          className={({ isActive }) =>
            `flex flex-col items-center justify-center px-3 py-1.5 rounded-full min-w-[58px] transition-colors ${
              isActive ? "text-[#59745D]" : "text-[#9A9F9D]"
            }`
          }
          data-testid={`mobile-nav-${label.toLowerCase()}`}
        >
          <Icon size={18} strokeWidth={1.5} />
          <span className="text-[10px] mt-0.5 tracking-wide">{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
