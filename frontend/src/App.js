import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import Sidebar from "./components/Sidebar";
import MobileNav from "./components/MobileNav";
import Today from "./pages/Today";
import Tomorrow from "./pages/Tomorrow";
import Blueprint from "./pages/Blueprint";
import Fitness from "./pages/Fitness";
import Recipes from "./pages/Recipes";
import Companion from "./pages/Companion";
import Motivation from "./pages/Motivation";
import Meditate from "./pages/Meditate";
import SelfCare from "./pages/SelfCare";
import Events from "./pages/Events";
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
          <Route path="/companion" element={<Companion />} />
          <Route path="/motivation" element={<Motivation />} />
          <Route path="/meditate" element={<Meditate />} />
          <Route path="/self-care" element={<SelfCare />} />
          <Route path="/events" element={<Events />} />
        </Routes>
      </main>
      <MobileNav />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
      <Toaster position="top-center" richColors theme="light" />
    </BrowserRouter>
  );
}
