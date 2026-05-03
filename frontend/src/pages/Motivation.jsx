import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Container, Card, Eyebrow, PageHeader } from "../components/Layout";
import { Quote as QuoteIcon, Play, Trash2, Shuffle } from "lucide-react";
import { YouTubeThumb, WatchOnYouTube } from "../components/YouTubeThumb";
import AddYouTubeDialog from "../components/AddYouTubeDialog";
import { toast } from "sonner";

export default function Motivation() {
  const [quotes, setQuotes] = useState([]);
  const [podcasts, setPodcasts] = useState([]);
  const [activeCat, setActiveCat] = useState("All");
  const [playing, setPlaying] = useState(null);
  const [shuffled, setShuffled] = useState({}); // slot.id -> replacement podcast

  const loadPodcasts = () => api.get("/podcasts").then(r => { setPodcasts(r.data); setShuffled({}); });

  useEffect(() => {
    (async () => {
      const [q, p] = await Promise.all([api.get("/quotes"), api.get("/podcasts")]);
      setQuotes(q.data); setPodcasts(p.data);
    })();
  }, []);

  const deletePodcast = async (id) => {
    if (!window.confirm("Remove this from your library?")) return;
    try {
      await api.delete(`/podcasts/${id}`);
      setPodcasts(p => p.filter(x => x.id !== id));
      toast.success("Removed");
    } catch {
      toast.error("Couldn't remove");
    }
  };

  // Cards display: each slot shows either the original podcast or a shuffled replacement
  const displayed = podcasts.map(p => shuffled[p.id] || p);

  const tryAnother = (slotId) => {
    const current = displayed.find(d => d && (shuffled[slotId]?.id === d.id || slotId === d.id));
    const currentYid = (shuffled[slotId] || podcasts.find(p => p.id === slotId))?.youtube_id;
    const candidates = podcasts.filter(p => p.youtube_id !== currentYid);
    if (candidates.length === 0) {
      toast.message("Add more to your library to shuffle");
      return;
    }
    const pick = candidates[Math.floor(Math.random() * candidates.length)];
    setShuffled(s => ({ ...s, [slotId]: pick }));
    if (playing === slotId) setPlaying(null); // stop the old embed
  };

  const cats = ["All", ...Array.from(new Set(quotes.map(q => q.category)))];
  const filteredQuotes = activeCat === "All" ? quotes : quotes.filter(q => q.category === activeCat);

  // Quotes rotation — show 6 random ones at a time
  const QUOTE_BATCH_SIZE = 6;
  const [quoteSeed, setQuoteSeed] = useState(0);
  const visibleQuotes = React.useMemo(() => {
    if (filteredQuotes.length === 0) return [];
    // Fisher-Yates shuffle, then take first N
    const arr = [...filteredQuotes];
    // Use seed to derive pseudorandom order for this batch
    let s = quoteSeed || 1;
    for (let i = arr.length - 1; i > 0; i--) {
      s = (s * 9301 + 49297) % 233280;
      const j = Math.floor((s / 233280) * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr.slice(0, QUOTE_BATCH_SIZE);
  }, [filteredQuotes, quoteSeed]);

  // Reshuffle when category changes
  useEffect(() => {
    setQuoteSeed(Math.floor(Math.random() * 1e9));
  }, [activeCat]);

  return (
    <Container>
      <PageHeader
        eyebrow="Fuel for the soul"
        title="Wisdom, quietly collected."
        subtitle="Lines to return to when the days feel heavy. Voices to listen to when you need to remember."
        image="https://static.prod-images.emergentagent.com/jobs/b8c548de-315f-4118-954b-1d59454f577f/images/089d41eba1d432a1fa65b246e0d0a157f3fd5d31d0135f2274dbded8c0379d43.png"
      />

      {/* Podcasts */}
      <section className="mb-14" data-testid="podcasts-section">
        <div className="flex items-baseline justify-between mb-5 gap-4 flex-wrap">
          <div>
            <Eyebrow>Listen</Eyebrow>
            <h2 className="font-serif text-3xl text-[#2D312E]">Speeches & podcasts</h2>
          </div>
          <AddYouTubeDialog
            kind="podcast"
            categories={["Wisdom", "Discipline", "Philosophy", "Motivation", "Peace", "Spiritual"]}
            onAdded={loadPodcasts}
          />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {podcasts.map(slot => {
            const p = shuffled[slot.id] || slot;
            const isPlaying = playing === slot.id;
            return (
            <Card key={slot.id} className="p-0 overflow-hidden relative" data-testid={`podcast-${slot.id}`}>
              <button
                onClick={(e) => { e.stopPropagation(); tryAnother(slot.id); }}
                className="absolute top-3 right-3 z-10 w-9 h-9 rounded-full bg-white/90 hover:bg-white border border-sand flex items-center justify-center shadow-sm transition-transform hover:rotate-180"
                title="Try another"
                data-testid={`shuffle-podcast-${slot.id}`}
              >
                <Shuffle size={14} strokeWidth={1.5} className="text-[#2D312E]"/>
              </button>
              {isPlaying ? (
                <div className="aspect-video bg-black rounded-t-3xl overflow-hidden">
                  <iframe
                    src={`https://www.youtube.com/embed/${p.youtube_id}?autoplay=1&rel=0`}
                    title={p.title} allow="autoplay; encrypted-media" allowFullScreen
                    className="w-full h-full"
                  />
                </div>
              ) : (
                <button
                  onClick={() => setPlaying(slot.id)}
                  className="aspect-video w-full relative group block"
                  data-testid={`play-podcast-${slot.id}`}
                >
                  <YouTubeThumb youtubeId={p.youtube_id} title={p.title} className="absolute inset-0" />
                  <div className="absolute inset-0 bg-black/40 group-hover:bg-black/30 transition-colors flex items-center justify-center">
                    <div className="w-16 h-16 rounded-full bg-white/90 flex items-center justify-center group-hover:scale-110 transition-transform">
                      <Play size={24} strokeWidth={1.5} className="ml-1 text-[#2D312E]" />
                    </div>
                  </div>
                </button>
              )}
              <div className="p-5">
                <p className="text-[11px] uppercase tracking-widest text-[#C27A62]">{p.category} · {p.duration}</p>
                <h3 className="font-serif text-xl text-[#2D312E] mt-1">{p.title}</h3>
                <div className="flex items-center justify-between mt-1 gap-2">
                  <p className="text-sm text-[#6B7270] truncate">{p.host}</p>
                  <div className="flex items-center gap-3 shrink-0">
                    <WatchOnYouTube youtubeId={p.youtube_id} />
                    {p.is_custom && (
                      <button
                        onClick={(e) => { e.stopPropagation(); deletePodcast(p.id); }}
                        className="text-[#9A9F9D] hover:text-[#B85C50]"
                        title="Remove from library"
                        data-testid={`delete-podcast-${p.id}`}
                      >
                        <Trash2 size={13} strokeWidth={1.5}/>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </Card>
          );})}
        </div>
      </section>

      {/* Quotes */}
      <section data-testid="quotes-section">
        <div className="flex items-baseline justify-between mb-5 gap-4 flex-wrap">
          <div>
            <Eyebrow>Read</Eyebrow>
            <h2 className="font-serif text-3xl text-[#2D312E]">Lines worth memorizing</h2>
          </div>
          <button
            onClick={() => setQuoteSeed(Math.floor(Math.random() * 1e9))}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#F4F1EA] hover:bg-sand text-[#59745D] text-sm transition-colors group"
            data-testid="refresh-quotes-btn"
          >
            <Shuffle size={14} strokeWidth={1.5} className="transition-transform group-hover:rotate-180"/>
            Fresh batch
          </button>
        </div>
        <div className="flex flex-wrap gap-2 mb-6">
          {cats.map(c => (
            <button
              key={c}
              onClick={() => setActiveCat(c)}
              className={`px-4 py-1.5 rounded-full text-xs tracking-wider uppercase transition-colors ${
                activeCat === c ? "bg-[#59745D] text-white" : "bg-[#F4F1EA] text-[#6B7270] hover:bg-sand"
              }`}
              data-testid={`quote-cat-${c}`}
            >{c}</button>
          ))}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {visibleQuotes.map((q, i) => (
            <Card key={`${quoteSeed}-${i}`} data-testid={`quote-${i}`} className="relative animate-in fade-in duration-500">
              <QuoteIcon size={20} strokeWidth={1.5} className="text-[#C27A62] mb-3" />
              <p className="font-serif text-2xl leading-snug text-[#2D312E]">"{q.text}"</p>
              <p className="text-xs text-[#9A9F9D] mt-4 uppercase tracking-widest">— {q.author}</p>
            </Card>
          ))}
          {visibleQuotes.length === 0 && (
            <p className="md:col-span-2 text-center text-[#6B7270] py-10">No quotes in this category yet.</p>
          )}
        </div>
      </section>
    </Container>
  );
}
