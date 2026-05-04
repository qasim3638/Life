import React, { useEffect, useState, useCallback } from "react";
import { X, ChevronLeft, ChevronRight, Volume2, VolumeX, Shuffle } from "lucide-react";

/**
 * Full-screen immersive player for Sanctuary.
 * - Sounds: nature still as backdrop + hidden YouTube audio loop
 * - Scenery: YouTube video filling the screen
 * - Stills: high-res image with optional drift/zoom animation
 *
 * Closes on ESC, on backdrop click, on the explicit close button.
 */
export default function SanctuaryMode({ kind, item, items, stills, onClose, onChange }) {
  const [muted, setMuted] = useState(false);
  const [stillIdx, setStillIdx] = useState(0);

  // Pre-pick a backdrop still for sound mode (deterministic per item id)
  const backdropStill = React.useMemo(() => {
    if (!stills || stills.length === 0) return null;
    if (kind !== "sounds") return null;
    const seed = (item?.id || "").split("").reduce((a, c) => a + c.charCodeAt(0), 0);
    return stills[seed % stills.length];
  }, [kind, item?.id, stills]);

  // For stills mode: index into the stills array
  useEffect(() => {
    if (kind === "stills" && item && stills) {
      const idx = stills.findIndex(s => s.id === item.id);
      if (idx >= 0) setStillIdx(idx);
    }
  }, [kind, item, stills]);

  const close = useCallback(() => onClose(), [onClose]);

  const goNext = useCallback(() => {
    if (kind === "stills" && stills?.length) {
      setStillIdx(i => (i + 1) % stills.length);
    } else if (items?.length && item) {
      const i = items.findIndex(x => x.id === item.id);
      const next = items[(i + 1) % items.length];
      onChange?.(next);
    }
  }, [kind, items, item, stills, onChange]);

  const goPrev = useCallback(() => {
    if (kind === "stills" && stills?.length) {
      setStillIdx(i => (i - 1 + stills.length) % stills.length);
    } else if (items?.length && item) {
      const i = items.findIndex(x => x.id === item.id);
      const prev = items[(i - 1 + items.length) % items.length];
      onChange?.(prev);
    }
  }, [kind, items, item, stills, onChange]);

  const shuffle = useCallback(() => {
    if (kind === "stills" && stills?.length > 1) {
      let next = stillIdx;
      while (next === stillIdx) next = Math.floor(Math.random() * stills.length);
      setStillIdx(next);
    } else if (items?.length > 1 && item) {
      const others = items.filter(x => x.id !== item.id);
      const pick = others[Math.floor(Math.random() * others.length)];
      onChange?.(pick);
    }
  }, [kind, stills, items, item, stillIdx, onChange]);

  // Keyboard: ESC to close, ←/→ to navigate
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") close();
      else if (e.key === "ArrowRight") goNext();
      else if (e.key === "ArrowLeft") goPrev();
      else if (e.key === " " && kind !== "stills") { /* let YT iframe handle */ }
      else if (e.key.toLowerCase() === "m" && kind === "sounds") setMuted(m => !m);
    };
    window.addEventListener("keydown", onKey);
    // Lock body scroll while immersive
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [close, goNext, goPrev, kind]);

  if (!item && kind !== "stills") return null;

  const stillUrl = (id, w = 2400) =>
    `https://images.unsplash.com/${id}?auto=format&fit=crop&w=${w}&q=80`;

  // ---- Sounds: full-bleed photo backdrop + hidden YouTube audio
  if (kind === "sounds") {
    const bgId = backdropStill?.id;
    return (
      <Shell onBackdropClick={close} data-testid="sanctuary-mode">
        {bgId && (
          <img
            src={stillUrl(bgId, 2000)}
            alt=""
            className="absolute inset-0 w-full h-full object-cover sanctuary-drift"
          />
        )}
        <div className="absolute inset-0 bg-black/40"/>
        {/* Hidden YT iframe playing audio */}
        <div className="absolute opacity-0 pointer-events-none -z-10 w-px h-px overflow-hidden">
          <iframe
            key={item.youtube_id + (muted ? "-m" : "")}
            src={`https://www.youtube.com/embed/${item.youtube_id}?autoplay=1&loop=1&playlist=${item.youtube_id}&controls=0&modestbranding=1&rel=0&mute=${muted ? 1 : 0}`}
            title={item.title}
            allow="autoplay; encrypted-media"
            className="w-px h-px"
          />
        </div>
        <Caption item={item}/>
        <Controls
          onClose={close}
          onPrev={goPrev}
          onNext={goNext}
          onShuffle={shuffle}
          rightExtra={
            <button
              onClick={() => setMuted(m => !m)}
              className="immersive-btn"
              title={muted ? "Unmute" : "Mute"}
              data-testid="immersive-mute"
            >
              {muted ? <VolumeX size={18} strokeWidth={1.5}/> : <Volume2 size={18} strokeWidth={1.5}/>}
            </button>
          }
        />
      </Shell>
    );
  }

  // ---- Scenery: video fills screen
  if (kind === "scenery") {
    return (
      <Shell onBackdropClick={close} data-testid="sanctuary-mode">
        <iframe
          key={item.youtube_id}
          src={`https://www.youtube.com/embed/${item.youtube_id}?autoplay=1&controls=1&modestbranding=1&rel=0`}
          title={item.title}
          allow="autoplay; encrypted-media; fullscreen"
          allowFullScreen
          className="absolute inset-0 w-full h-full"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-transparent to-black/40 pointer-events-none"/>
        <Caption item={item}/>
        <Controls onClose={close} onPrev={goPrev} onNext={goNext} onShuffle={shuffle}/>
      </Shell>
    );
  }

  // ---- Stills: high-res image, slow drift
  const cur = stills?.[stillIdx];
  if (!cur) return null;
  return (
    <Shell onBackdropClick={close} data-testid="sanctuary-mode">
      <img
        key={cur.id}
        src={stillUrl(cur.id, 2400)}
        alt={cur.title}
        className="absolute inset-0 w-full h-full object-cover sanctuary-drift"
      />
      <div className="absolute inset-0 bg-black/15"/>
      <Caption item={cur}/>
      <Controls onClose={close} onPrev={goPrev} onNext={goNext} onShuffle={shuffle}/>
    </Shell>
  );
}

function Shell({ children, onBackdropClick, ...rest }) {
  return (
    <div
      className="fixed inset-0 z-[100] bg-black overflow-hidden animate-fade-in"
      onClick={(e) => {
        if (e.target === e.currentTarget) onBackdropClick?.();
      }}
      {...rest}
    >
      {children}
    </div>
  );
}

function Caption({ item }) {
  if (!item) return null;
  return (
    <div className="absolute left-0 right-0 bottom-24 sm:bottom-28 px-6 sm:px-10 pointer-events-none animate-fade-in-up">
      <p className="text-[10px] uppercase tracking-[0.3em] text-white/70">
        {item.category}{item.duration ? ` · ${item.duration}` : ""}
      </p>
      <h2 className="font-serif text-white text-3xl sm:text-5xl leading-tight mt-1 max-w-3xl drop-shadow-[0_2px_12px_rgba(0,0,0,0.4)]">
        {item.title}
      </h2>
    </div>
  );
}

function Controls({ onClose, onPrev, onNext, onShuffle, rightExtra }) {
  return (
    <>
      {/* Top right: close */}
      <button
        onClick={onClose}
        className="absolute top-5 right-5 w-11 h-11 rounded-full bg-white/15 hover:bg-white/25 backdrop-blur text-white flex items-center justify-center transition-colors"
        aria-label="Exit immersive mode"
        data-testid="immersive-close"
        title="Exit (Esc)"
      >
        <X size={20} strokeWidth={1.5}/>
      </button>

      {/* Bottom centre: prev / shuffle / next + extras */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-3">
        <button onClick={onPrev} className="immersive-btn" title="Previous (←)" data-testid="immersive-prev">
          <ChevronLeft size={20} strokeWidth={1.5}/>
        </button>
        <button onClick={onShuffle} className="immersive-btn" title="Shuffle" data-testid="immersive-shuffle">
          <Shuffle size={16} strokeWidth={1.5}/>
        </button>
        <button onClick={onNext} className="immersive-btn" title="Next (→)" data-testid="immersive-next">
          <ChevronRight size={20} strokeWidth={1.5}/>
        </button>
        {rightExtra}
      </div>
    </>
  );
}
