import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Container, Card, PageHeader } from "../components/Layout";
import { YouTubeThumb, WatchOnYouTube } from "../components/YouTubeThumb";
import AddYouTubeDialog from "../components/AddYouTubeDialog";
import SanctuaryMode from "../components/sanctuary/SanctuaryMode";
import { Play, Trash2, Shuffle, Waves, TreePine, Image as ImageIcon, Maximize2, Sparkles } from "lucide-react";
import { toast } from "sonner";

const HERO_IMG = "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?auto=format&fit=crop&w=1600&q=70";

const TABS = [
  { key: "sounds", label: "Sounds", icon: Waves, endpoint: "/sanctuary/sounds",
    cats: ["Rain", "Ocean", "Forest", "Thunderstorm", "Fire", "Stream"] },
  { key: "scenery", label: "Scenery", icon: TreePine, endpoint: "/sanctuary/scenery",
    cats: ["Aerial", "Wildlife", "Cinematic", "Worldwide", "Ocean", "Forest"] },
  { key: "stills", label: "Stills", icon: ImageIcon, endpoint: "/sanctuary/stills" },
];

function ContentCard({ item, onPlay, onImmersive, onShuffle, onDelete, shuffleTid }) {
  return (
    <Card className="p-0 overflow-hidden relative cursor-pointer group" onClick={() => onPlay(item)} data-testid={`sanctuary-item-${item.id}`}>
      <div className="absolute top-3 right-3 z-10 flex gap-2">
        <button
          onClick={(e) => { e.stopPropagation(); onImmersive(item); }}
          className="w-9 h-9 rounded-full bg-white/90 hover:bg-white border border-sand flex items-center justify-center shadow-sm"
          title="Open in Sanctuary mode"
          data-testid={`immersive-${item.id}`}
        >
          <Maximize2 size={14} strokeWidth={1.5} className="text-[#2D312E]"/>
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onShuffle(item.id); }}
          className="w-9 h-9 rounded-full bg-white/90 hover:bg-white border border-sand flex items-center justify-center shadow-sm transition-transform hover:rotate-180"
          title="Try another"
          data-testid={shuffleTid}
        >
          <Shuffle size={14} strokeWidth={1.5} className="text-[#2D312E]"/>
        </button>
      </div>
      <div className="aspect-video relative">
        <YouTubeThumb youtubeId={item.youtube_id} title={item.title} className="absolute inset-0"/>
        <div className="absolute inset-0 bg-black/40 group-hover:bg-black/30 transition-colors flex items-center justify-center">
          <div className="w-16 h-16 rounded-full bg-white/90 flex items-center justify-center group-hover:scale-110 transition-transform">
            <Play size={22} strokeWidth={1.5} className="ml-1 text-[#2D312E]"/>
          </div>
        </div>
      </div>
      <div className="p-4">
        <p className="text-[10px] uppercase tracking-widest text-[#C27A62]">{item.category} · {item.duration}</p>
        <h3 className="font-serif text-lg text-[#2D312E] mt-0.5 leading-tight">{item.title}</h3>
        {item.description && <p className="text-xs text-[#6B7270] mt-1 line-clamp-2">{item.description}</p>}
        <div className="flex items-center justify-between mt-2 gap-2">
          <WatchOnYouTube youtubeId={item.youtube_id}/>
          {item.is_custom && (
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(item.id); }}
              className="text-[#9A9F9D] hover:text-[#B85C50]"
              title="Remove"
              data-testid={`delete-${item.id}`}
            >
              <Trash2 size={13} strokeWidth={1.5}/>
            </button>
          )}
        </div>
      </div>
    </Card>
  );
}

export default function Sanctuary() {
  const [tab, setTab] = useState("sounds");
  const [sounds, setSounds] = useState([]);
  const [scenery, setScenery] = useState([]);
  const [stills, setStills] = useState([]);
  const [playing, setPlaying] = useState(null); // full item
  const [shuffled, setShuffled] = useState({});
  const [immersive, setImmersive] = useState(null); // { kind, item }

  const loadAll = async () => {
    const [s, v, p] = await Promise.all([
      api.get("/sanctuary/sounds"),
      api.get("/sanctuary/scenery"),
      api.get("/sanctuary/stills"),
    ]);
    setSounds(s.data);
    setScenery(v.data);
    setStills(p.data);
    setShuffled({});
  };

  useEffect(() => { loadAll(); }, []);

  const currentTab = TABS.find(t => t.key === tab);
  const items = tab === "sounds" ? sounds : tab === "scenery" ? scenery : [];

  const play = (item) => setPlaying(item);

  const openImmersive = (item, kind = tab) => setImmersive({ kind, item });
  const enterStillsImmersive = () => {
    if (!stills?.length) return toast.message("No stills loaded yet");
    setImmersive({ kind: "stills", item: stills[0] });
  };

  const shuffle = (slotId) => {
    const slotOrig = items.find(x => x.id === slotId);
    const currentYid = (shuffled[slotId] || slotOrig)?.youtube_id;
    const candidates = items.filter(x => x.youtube_id !== currentYid);
    if (candidates.length === 0) {
      toast.message("Add more to your library to shuffle");
      return;
    }
    const pick = candidates[Math.floor(Math.random() * candidates.length)];
    setShuffled(s => ({ ...s, [slotId]: pick }));
    if (playing && playing.id === slotId) setPlaying(pick);
  };

  const del = async (id) => {
    if (!window.confirm("Remove this?")) return;
    try {
      await api.delete(`${currentTab.endpoint}/${id}`);
      toast.success("Removed");
      loadAll();
    } catch { toast.error("Couldn't remove"); }
  };

  return (
    <Container>
      <PageHeader
        eyebrow="Sanctuary"
        title="A quiet place for a loud mind."
        subtitle="Sounds to settle into. Scenery to breathe with. Stills to rest your eyes on."
        image={HERO_IMG}
      />

      {/* Tabs */}
      <div className="flex items-center gap-2 mb-8 flex-wrap">
        {TABS.map(t => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => { setTab(t.key); setShuffled({}); }}
              className={`inline-flex items-center gap-2 px-5 py-2 rounded-full text-sm uppercase tracking-wider transition-colors ${
                active ? "bg-[#59745D] text-white" : "bg-[#F4F1EA] text-[#6B7270] hover:bg-sand"
              }`}
              data-testid={`sanctuary-tab-${t.key}`}
            >
              <Icon size={14} strokeWidth={1.5}/> {t.label}
            </button>
          );
        })}
        {(tab === "sounds" || tab === "scenery") && (
          <div className="ml-auto">
            <AddYouTubeDialog
              kind="sanctuary"
              categories={currentTab.cats}
              onAdded={loadAll}
              apiPath={currentTab.endpoint}
            />
          </div>
        )}
      </div>

      {/* Playing embed */}
      {playing && (tab === "sounds" || tab === "scenery") && (
        <div className="mb-8 rounded-3xl overflow-hidden bg-black relative" data-testid="sanctuary-player">
          <div className="aspect-video">
            <iframe
              src={`https://www.youtube.com/embed/${playing.youtube_id}?autoplay=1&rel=0`}
              title={playing.title}
              allow="autoplay; encrypted-media; fullscreen"
              allowFullScreen
              className="w-full h-full"
            />
          </div>
          <button
            onClick={() => openImmersive(playing)}
            className="absolute top-3 right-14 px-3 h-9 rounded-full bg-white/90 hover:bg-white text-[#2D312E] text-xs font-medium flex items-center gap-1.5"
            title="Open in Sanctuary mode"
            data-testid="enter-immersive-from-player"
          >
            <Sparkles size={12} strokeWidth={1.5}/> Sanctuary mode
          </button>
          <button
            onClick={() => setPlaying(null)}
            className="absolute top-3 right-3 w-9 h-9 rounded-full bg-white/90 hover:bg-white text-[#2D312E] text-sm flex items-center justify-center"
            aria-label="Close player"
            data-testid="close-player-btn"
          >
            ✕
          </button>
        </div>
      )}

      {/* Grid */}
      {(tab === "sounds" || tab === "scenery") && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {items.map(slot => {
            const item = shuffled[slot.id] || slot;
            return (
              <ContentCard
                key={slot.id}
                item={{ ...item, id: slot.id }}
                onPlay={play}
                onImmersive={openImmersive}
                onShuffle={shuffle}
                onDelete={del}
                shuffleTid={`shuffle-${slot.id}`}
              />
            );
          })}
          {items.length === 0 && (
            <p className="md:col-span-2 lg:col-span-3 text-center text-[#6B7270] py-10">Nothing here yet.</p>
          )}
        </div>
      )}

      {tab === "stills" && (
        <>
          <div className="mb-5 flex items-center justify-between gap-4 flex-wrap">
            <p className="text-sm text-[#6B7270] max-w-xl">
              Tap any still to drop into a calm, full-screen view. Use ← → to drift through the gallery.
            </p>
            <button
              onClick={enterStillsImmersive}
              className="inline-flex items-center gap-2 px-5 h-10 rounded-full bg-[#59745D] hover:bg-[#4a6350] text-white text-sm transition-colors"
              data-testid="stills-enter-immersive"
            >
              <Sparkles size={14} strokeWidth={1.5}/> Enter Sanctuary
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3" data-testid="stills-grid">
            {stills.map((s, i) => {
              const url = `https://images.unsplash.com/${s.id}?auto=format&fit=crop&w=800&q=70`;
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => setImmersive({ kind: "stills", item: s })}
                  className="block aspect-square rounded-2xl overflow-hidden group relative text-left"
                  data-testid={`still-${i}`}
                >
                  <img
                    src={url}
                    alt={s.title}
                    loading="lazy"
                    decoding="async"
                    width="800"
                    height="800"
                    className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-4">
                    <p className="font-serif text-white text-sm leading-tight">{s.title}</p>
                  </div>
                </button>
              );
            })}
            {stills.length === 0 && (
              <p className="col-span-full text-center text-[#6B7270] py-10">Loading…</p>
            )}
          </div>
        </>
      )}

      {immersive && (
        <SanctuaryMode
          kind={immersive.kind}
          item={immersive.item}
          items={immersive.kind === "sounds" ? sounds : immersive.kind === "scenery" ? scenery : null}
          stills={stills}
          onChange={(next) => setImmersive(im => ({ ...im, item: next }))}
          onClose={() => setImmersive(null)}
        />
      )}
    </Container>
  );
}
