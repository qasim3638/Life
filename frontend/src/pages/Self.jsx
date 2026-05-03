import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Container, Card, Eyebrow, PageHeader } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Sparkles, User, Heart, Brain, Shirt, Smartphone, Save } from "lucide-react";
import { toast } from "sonner";

const DIMENSIONS = [
  {
    key: "appearance",
    label: "Appearance",
    icon: User,
    placeholder: "Height, build, hair, beard, skin, what you see in the mirror — and what you'd like to change with kindness.",
    eyebrow: "How you look",
    tagline: "The body you're in. Describe it without judgment.",
  },
  {
    key: "personality",
    label: "Personality",
    icon: Heart,
    placeholder: "Introvert / extrovert, what makes you laugh, your softness, your edges, what people say about you.",
    eyebrow: "Who you are",
    tagline: "The inner shape of you. The patterns. The strengths and the work in progress.",
  },
  {
    key: "mind",
    label: "Mind",
    icon: Brain,
    placeholder: "What you read, what you believe, what you're curious about, what you wrestle with.",
    eyebrow: "How you think",
    tagline: "Your interests, your beliefs, your inner library.",
  },
  {
    key: "style",
    label: "Style",
    icon: Shirt,
    placeholder: "Colors you love, fits that work, fabrics, formal vs casual ratio, brands or vibes that feel like you.",
    eyebrow: "How you dress",
    tagline: "Personal style is a quiet way of speaking.",
  },
  {
    key: "gear",
    label: "Gear",
    icon: Smartphone,
    placeholder: "Phone, watch, headphones, bags, pens, daily-carry items — and what's missing or worn out.",
    eyebrow: "What you carry",
    tagline: "Tools that age well. Things you use every day.",
  },
];

export default function Self() {
  const [tab, setTab] = useState("appearance");
  const [profile, setProfile] = useState(null);
  const [draft, setDraft] = useState({});
  const [savingTab, setSavingTab] = useState(null);
  const [aiText, setAiText] = useState("");
  const [aiLoading, setAiLoading] = useState(false);

  const load = async () => {
    const { data } = await api.get("/self-profile");
    setProfile(data);
    setDraft({
      appearance: data.appearance || "",
      personality: data.personality || "",
      mind: data.mind || "",
      style: data.style || "",
      gear: data.gear || "",
    });
  };
  useEffect(() => { load(); }, []);

  useEffect(() => { setAiText(""); }, [tab]);

  const save = async () => {
    setSavingTab(tab);
    try {
      const { data } = await api.put("/self-profile", { [tab]: draft[tab] });
      setProfile(data);
      toast.success("Saved");
    } catch { toast.error("Couldn't save"); }
    finally { setSavingTab(null); }
  };

  const askAI = async () => {
    setAiLoading(true); setAiText("");
    try {
      const { data } = await api.post(`/ai/self-suggestion/${tab}`, {});
      setAiText(data.text);
    } catch { toast.error("AI is resting"); }
    finally { setAiLoading(false); }
  };

  const dim = DIMENSIONS.find(d => d.key === tab);
  if (!profile) return <Container><p className="text-[#6B7270]">Loading…</p></Container>;
  const Icon = dim.icon;
  const dirty = (draft[tab] || "") !== (profile[tab] || "");

  return (
    <Container>
      <PageHeader
        eyebrow="The art of being you"
        title="Self-love is paying attention."
        subtitle="Describe yourself across five dimensions. The companion uses this to give you suggestions that fit only you."
      />

      <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-8">
        <nav className="flex lg:flex-col gap-2 overflow-x-auto lg:overflow-visible -mx-6 px-6 lg:mx-0 lg:px-0">
          {DIMENSIONS.map(d => {
            const D = d.icon;
            const filled = ((profile[d.key] || "").trim().length > 0);
            return (
              <button
                key={d.key}
                onClick={() => setTab(d.key)}
                className={`flex items-center gap-3 px-4 py-3 rounded-2xl text-left transition-colors shrink-0 lg:shrink ${
                  tab === d.key
                    ? "bg-[#59745D] text-white"
                    : "bg-[#F4F1EA] text-[#2D312E] hover:bg-sand"
                }`}
                data-testid={`self-tab-${d.key}`}
              >
                <D size={16} strokeWidth={1.5} className="shrink-0"/>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm">{d.label}</p>
                  <p className={`text-[11px] ${tab === d.key ? "text-white/70" : "text-[#9A9F9D]"}`}>{d.eyebrow}</p>
                </div>
                {filled && (
                  <span className={`w-1.5 h-1.5 rounded-full ${tab === d.key ? "bg-white" : "bg-[#C27A62]"}`}/>
                )}
              </button>
            );
          })}
        </nav>

        <div className="space-y-6">
          <Card data-testid={`self-card-${tab}`}>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-full bg-[#F4F1EA] flex items-center justify-center">
                <Icon size={18} strokeWidth={1.5} className="text-[#59745D]"/>
              </div>
              <div>
                <Eyebrow>{dim.eyebrow}</Eyebrow>
                <h2 className="font-serif text-2xl text-[#2D312E] leading-tight">{dim.label}</h2>
              </div>
            </div>
            <p className="text-sm text-[#6B7270] leading-relaxed mt-1 mb-4">{dim.tagline}</p>
            <Textarea
              value={draft[tab] || ""}
              onChange={(e) => setDraft({ ...draft, [tab]: e.target.value })}
              placeholder={dim.placeholder}
              rows={8}
              className="resize-y"
              data-testid={`self-textarea-${tab}`}
            />
            <div className="flex flex-wrap items-center gap-2 mt-4">
              <Button onClick={save} disabled={!dirty || savingTab === tab} className="rounded-full bg-[#59745D] hover:bg-[#4A604D]" data-testid={`save-${tab}-btn`}>
                <Save size={14} strokeWidth={1.5} className="mr-1"/>
                {savingTab === tab ? "Saving…" : "Save"}
              </Button>
              <Button onClick={askAI} disabled={aiLoading || !(draft[tab] || "").trim()} variant="outline" className="rounded-full border-[#C27A62] text-[#C27A62] hover:bg-[#C27A62] hover:text-white" data-testid={`suggest-${tab}-btn`}>
                <Sparkles size={14} strokeWidth={1.5} className="mr-1"/>
                {aiLoading ? "Thinking…" : `Suggest for ${dim.label.toLowerCase()}`}
              </Button>
            </div>
          </Card>

          {aiText && (
            <Card className="bg-[#F4F1EA] border-0" data-testid="suggestion-card">
              <Eyebrow>Suggestions</Eyebrow>
              <p className="font-serif text-base md:text-lg text-[#2D312E] mt-2 leading-relaxed whitespace-pre-wrap">{aiText}</p>
            </Card>
          )}
        </div>
      </div>
    </Container>
  );
}
