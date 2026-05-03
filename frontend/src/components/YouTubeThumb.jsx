import React, { useState } from "react";
import { Play, ExternalLink } from "lucide-react";

/**
 * Renders a YouTube thumbnail with graceful fallback.
 * If YouTube returns the 120x90 "no image" grey placeholder (broken/deleted video),
 * we show a warm, title-based placeholder instead.
 * Props: youtubeId, title, className, aspect = "video"
 */
export function YouTubeThumb({ youtubeId, title, className = "" }) {
  const [broken, setBroken] = useState(false);

  if (broken) {
    return (
      <div className={`relative flex items-center justify-center bg-gradient-to-br from-[#F4F1EA] via-[#FAF6EC] to-[#E8E2D2] ${className}`}>
        <div className="text-center px-6">
          <div className="w-14 h-14 mx-auto rounded-full bg-white/80 border border-sand flex items-center justify-center">
            <Play size={22} strokeWidth={1.5} className="ml-0.5 text-[#59745D]"/>
          </div>
          <p className="font-serif text-[#2D312E] text-lg mt-3 leading-tight line-clamp-2">{title}</p>
          <p className="text-[10px] uppercase tracking-[0.25em] text-[#A3897C] mt-1">Watch on YouTube</p>
        </div>
      </div>
    );
  }

  return (
    <img
      src={`https://i.ytimg.com/vi/${youtubeId}/hqdefault.jpg`}
      alt={title}
      loading="lazy"
      decoding="async"
      onLoad={(e) => {
        // YouTube returns 120x90 grey placeholder for dead videos
        if (e.currentTarget.naturalWidth > 0 && e.currentTarget.naturalWidth <= 120) {
          setBroken(true);
        }
      }}
      onError={() => setBroken(true)}
      className={`w-full h-full object-cover ${className}`}
    />
  );
}

export function WatchOnYouTube({ youtubeId, className = "" }) {
  return (
    <a
      href={`https://www.youtube.com/watch?v=${youtubeId}`}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => e.stopPropagation()}
      className={`inline-flex items-center gap-1 text-[11px] uppercase tracking-widest text-[#6B7270] hover:text-[#59745D] transition-colors ${className}`}
      data-testid={`yt-link-${youtubeId}`}
    >
      Watch on YouTube <ExternalLink size={11} strokeWidth={1.5}/>
    </a>
  );
}
