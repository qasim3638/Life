import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import AuthGate from "./components/AuthGate";
import Sidebar from "./components/Sidebar";
import MobileNav from "./components/MobileNav";
import { PlayerProvider } from "./components/Player";
import Today from "./pages/Today";
import Tomorrow from "./pages/Tomorrow";
import Blueprint from "./pages/Blueprint";
import Fitness from "./pages/Fitness";
import Recipes from "./pages/Recipes";
import Self from "./pages/Self";
import Focus from "./pages/Focus";
import Sobriety from "./pages/Sobriety";
import Family from "./pages/Family";
import Companion from "./pages/Companion";
import Motivation from "./pages/Motivation";
import Meditate from "./pages/Meditate";
import SelfCare from "./pages/SelfCare";
import Events from "./pages/Events";
import Review from "./pages/Review";
import Sanctuary from "./pages/Sanctuary";
import VoiceMicButton from "./components/VoiceMicButton";
import BriefScheduler from "./components/BriefScheduler";
import "./App.css";

function Shell() {
  return (
    <div className="flex bg-base min-h-screen">
      <Sidebar />
      <main className="flex-1 pb-24 lg:pb-0">
        <Routes>
          <Route path="/" element={<Today />} />
          <Route path="/tomorrow" element={<Tomorrow />} />
          <Route path="/blueprint" element={<Blueprint />} />
          <Route path="/fitness" element={<Fitness />} />
          <Route path="/recipes" element={<Recipes />} />
          <Route path="/family" element={<Family />} />
          <Route path="/self" element={<Self />} />
          <Route path="/focus" element={<Focus />} />
          <Route path="/sobriety" element={<Sobriety />} />
          <Route path="/companion" element={<Companion />} />
          <Route path="/motivation" element={<Motivation />} />
          <Route path="/meditate" element={<Meditate />} />
          <Route path="/self-care" element={<SelfCare />} />
          <Route path="/events" element={<Events />} />
          <Route path="/review" element={<Review />} />
          <Route path="/sanctuary" element={<Sanctuary />} />
        </Routes>
      </main>
      <MobileNav />
      <VoiceMicButton />
      <BriefScheduler />
    </div>
  );
}

export default function App() {
  return (
    <AuthGate>
      <BrowserRouter>
        <PlayerProvider>
          <Shell />
          <Toaster position="top-center" richColors theme="light" />
        </PlayerProvider>
      </BrowserRouter>
    </AuthGate>
  );
}
