import React, { createContext, useContext, useState } from "react";
import { X, Pause, Play, Music } from "lucide-react";

const PlayerCtx = createContext(null);

export function PlayerProvider({ children }) {
  const [track, setTrack] = useState(null); // { youtube_id, title, category }
  const [paused, setPaused] = useState(false);

  const play = (t) => { setTrack(t); setPaused(false); };
  const stop = () => { setTrack(null); setPaused(false); };
  const toggle = () => setPaused((p) => !p);

  return (
    <PlayerCtx.Provider value={{ track, paused, play, stop, toggle }}>
      {children}
      {track && (
        <div className="fixed bottom-20 lg:bottom-4 right-4 z-[60] bg-white border border-sand rounded-3xl shadow-xl p-3 flex items-center gap-3 max-w-[360px]" data-testid="mini-player">
          <iframe
            key={track.youtube_id + (paused ? "-p" : "")}
            src={`https://www.youtube.com/embed/${track.youtube_id}?autoplay=${paused ? 0 : 1}&rel=0&modestbranding=1`}
            title={track.title}
            allow="autoplay; encrypted-media"
            className="w-0 h-0 opacity-0 pointer-events-none absolute"
          />
          <div className="w-10 h-10 rounded-full bg-[#F4F1EA] flex items-center justify-center shrink-0">
            <Music size={16} strokeWidth={1.5} className={`text-[#59745D] ${paused ? "" : "animate-pulse"}`} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[10px] uppercase tracking-widest text-[#C27A62]">{track.category}</p>
            <p className="font-serif text-sm text-[#2D312E] truncate">{track.title}</p>
          </div>
          <button onClick={toggle} className="w-8 h-8 rounded-full bg-[#59745D] text-white flex items-center justify-center" data-testid="player-toggle">
            {paused ? <Play size={13}/> : <Pause size={13}/>}
          </button>
          <button onClick={stop} className="w-8 h-8 rounded-full bg-[#F4F1EA] text-[#6B7270] flex items-center justify-center" data-testid="player-stop">
            <X size={14}/>
          </button>
        </div>
      )}
    </PlayerCtx.Provider>
  );
}

export const usePlayer = () => useContext(PlayerCtx);
