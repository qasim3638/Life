import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Container, Card, Eyebrow, PageHeader } from "../components/Layout";
import { Quote as QuoteIcon, Play } from "lucide-react";
import { YouTubeThumb, WatchOnYouTube } from "../components/YouTubeThumb";

export default function Motivation() {
  const [quotes, setQuotes] = useState([]);
  const [podcasts, setPodcasts] = useState([]);
  const [activeCat, setActiveCat] = useState("All");
  const [playing, setPlaying] = useState(null);

  useEffect(() => {
    (async () => {
      const [q, p] = await Promise.all([api.get("/quotes"), api.get("/podcasts")]);
      setQuotes(q.data); setPodcasts(p.data);
    })();
  }, []);

  const cats = ["All", ...Array.from(new Set(quotes.map(q => q.category)))];
  const filteredQuotes = activeCat === "All" ? quotes : quotes.filter(q => q.category === activeCat);

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
        <div className="flex items-baseline justify-between mb-5">
          <div>
            <Eyebrow>Listen</Eyebrow>
            <h2 className="font-serif text-3xl text-[#2D312E]">Speeches & podcasts</h2>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {podcasts.map(p => (
            <Card key={p.id} className="p-0 overflow-hidden" data-testid={`podcast-${p.id}`}>
              {playing === p.id ? (
                <div className="aspect-video bg-black rounded-t-3xl overflow-hidden">
                  <iframe
                    src={`https://www.youtube.com/embed/${p.youtube_id}?autoplay=1&rel=0`}
                    title={p.title} allow="autoplay; encrypted-media" allowFullScreen
                    className="w-full h-full"
                  />
                </div>
              ) : (
                <button
                  onClick={() => setPlaying(p.id)}
                  className="aspect-video w-full relative group block"
                  data-testid={`play-podcast-${p.id}`}
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
                <div className="flex items-center justify-between mt-1">
                  <p className="text-sm text-[#6B7270]">{p.host}</p>
                  <WatchOnYouTube youtubeId={p.youtube_id} />
                </div>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* Quotes */}
      <section data-testid="quotes-section">
        <div className="flex items-baseline justify-between mb-5">
          <div>
            <Eyebrow>Read</Eyebrow>
            <h2 className="font-serif text-3xl text-[#2D312E]">Lines worth memorizing</h2>
          </div>
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
          {filteredQuotes.map((q, i) => (
            <Card key={i} data-testid={`quote-${i}`} className="relative">
              <QuoteIcon size={20} strokeWidth={1.5} className="text-[#C27A62] mb-3" />
              <p className="font-serif text-2xl leading-snug text-[#2D312E]">"{q.text}"</p>
              <p className="text-xs text-[#9A9F9D] mt-4 uppercase tracking-widest">— {q.author}</p>
            </Card>
          ))}
        </div>
      </section>
    </Container>
  );
}
