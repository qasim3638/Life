import React from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  Home, Dumbbell, UtensilsCrossed, Sparkles, Brain,
  Heart, CalendarDays, Compass, MessageCircle, Sunrise, Users, User as UserIcon,
  Timer, Shield as ShieldIcon, BookOpen, TreePine, Bell,
} from "lucide-react";

const items = [
  { to: "/", label: "Today", icon: Home, testid: "nav-today" },
  { to: "/tomorrow", label: "Tomorrow", icon: Sunrise, testid: "nav-tomorrow" },
  { to: "/focus", label: "Focus", icon: Timer, testid: "nav-focus" },
  { to: "/sobriety", label: "Sobriety", icon: ShieldIcon, testid: "nav-sobriety" },
  { to: "/blueprint", label: "Blueprint", icon: Compass, testid: "nav-blueprint" },
  { to: "/family", label: "Family", icon: Users, testid: "nav-family" },
  { to: "/self", label: "Self", icon: UserIcon, testid: "nav-self" },
  { to: "/companion", label: "Companion", icon: MessageCircle, testid: "nav-companion" },
  { to: "/fitness", label: "Fitness", icon: Dumbbell, testid: "nav-fitness" },
  { to: "/recipes", label: "Recipes", icon: UtensilsCrossed, testid: "nav-recipes" },
  { to: "/motivation", label: "Motivation", icon: Sparkles, testid: "nav-motivation" },
  { to: "/meditate", label: "Meditate", icon: Brain, testid: "nav-meditate" },
  { to: "/self-care", label: "Self-Care", icon: Heart, testid: "nav-selfcare" },
  { to: "/events", label: "Events", icon: CalendarDays, testid: "nav-events" },
  { to: "/reminders", label: "Reminders", icon: Bell, testid: "nav-reminders" },
  { to: "/review", label: "Sunday Review", icon: BookOpen, testid: "nav-review" },
  { to: "/sanctuary", label: "Sanctuary", icon: TreePine, testid: "nav-sanctuary" },
];

export default function Sidebar() {
  const loc = useLocation();
  return (
    <aside
      className="hidden lg:flex flex-col w-64 min-h-screen sticky top-0 px-6 py-8 border-r border-sand bg-[#FDFBF7]"
      data-testid="app-sidebar"
    >
      <div className="mb-10">
        <p className="text-xs tracking-[0.3em] uppercase text-[#9A9F9D]">Life</p>
        <h1 className="font-serif text-3xl text-[#2D312E] leading-none mt-1">
          Blueprint
        </h1>
        <p className="text-sm text-[#6B7270] mt-2 leading-relaxed">
          Forty more years.<br/>One honest day at a time.
        </p>
      </div>
      <nav className="flex flex-col gap-1">
        {items.map(({ to, label, icon: Icon, testid }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            data-testid={testid}
            className={({ isActive }) =>
              `group flex items-center gap-3 px-4 py-3 rounded-full transition-all
               ${isActive
                 ? "bg-[#59745D] text-white shadow-sm"
                 : "text-[#6B7270] hover:bg-[#F4F1EA] hover:text-[#2D312E]"}`
            }
          >
            <Icon
              size={18}
              strokeWidth={1.5}
              className="shrink-0"
            />
            <span className="text-sm tracking-wide">{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto pt-8">
        <div className="rounded-3xl p-5 bg-[#F4F1EA] border border-sand">
          <p className="font-serif text-lg text-[#2D312E] leading-snug">
            "What you seek is seeking you."
          </p>
          <p className="text-xs text-[#9A9F9D] mt-2">— Rumi</p>
        </div>
      </div>
    </aside>
  );
}
