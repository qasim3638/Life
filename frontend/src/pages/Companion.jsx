import React, { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { Container } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Send, Sparkles, Brain, Trash2, Settings, Star, Search, Lock } from "lucide-react";
import { toast } from "sonner";
import CompanionSidePanel, { PERSONAS } from "../components/companion/CompanionSidePanel";
import CompanionSettings from "../components/companion/CompanionSettings";
import MemoriesDialog from "../components/companion/MemoriesDialog";
import MemoryLaneDialog from "../components/companion/MemoryLaneDialog";
import ActionChips from "../components/companion/ActionChips";
import PinGate, { isUnlockedRecently, clearUnlock } from "../components/companion/PinGate";

export default function Companion() {
  const [companion, setCompanion] = useState(null);
  const [messages, setMessages] = useState([]);
  const [memories, setMemories] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [memoryLaneOpen, setMemoryLaneOpen] = useState(false);
  const [newMem, setNewMem] = useState({ content: "", category: "general" });
  const [pinEnabled, setPinEnabled] = useState(null); // null=unknown, true/false
  const [unlocked, setUnlocked] = useState(false);
  const scrollRef = useRef(null);

  const loadCompanionMeta = async () => {
    const [c, status] = await Promise.all([
      api.get("/companion"),
      api.get("/companion/pin/status"),
    ]);
    setCompanion(c.data);
    const enabled = !!status.data?.enabled;
    setPinEnabled(enabled);
    if (!enabled || isUnlockedRecently()) {
      setUnlocked(true);
    }
  };

  const loadProtected = async () => {
    const [m, mm] = await Promise.all([
      api.get("/companion/messages"),
      api.get("/companion/memories"),
    ]);
    setMessages(m.data);
    setMemories(mm.data);
  };

  useEffect(() => { loadCompanionMeta(); }, []);
  useEffect(() => {
    if (unlocked) loadProtected();
  }, [unlocked]);

  // If user arrived via "send to companion" from another page, ensure latest messages
  useEffect(() => {
    if (sessionStorage.getItem("companion_jump") === "1") {
      sessionStorage.removeItem("companion_jump");
      const t = setTimeout(() => { if (unlocked) loadProtected(); }, 1200);
      return () => clearTimeout(t);
    }
  }, [unlocked]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, sending]);

  const send = async () => {
    if (!input.trim() || sending) return;
    const text = input;
    setInput("");
    setSending(true);
    setMessages((m) => [...m, { id: "tmp-u", role: "user", content: text, created_at: new Date().toISOString() }]);
    try {
      await api.post("/companion/chat", { message: text });
      const m = await api.get("/companion/messages");
      setMessages(m.data);
    } catch {
      toast.error("Couldn't send. Try again.");
    } finally { setSending(false); }
  };

  const updateCompanion = async (patch) => {
    const { data } = await api.put("/companion", patch);
    setCompanion(data);
    toast.success("Saved");
  };

  const addMemory = async () => {
    if (!newMem.content.trim()) return toast.error("Write something to remember");
    try {
      await api.post("/companion/memories", newMem);
      setNewMem({ content: "", category: "general" });
      const mm = await api.get("/companion/memories");
      setMemories(mm.data);
      toast.success("Saved to memory");
    } catch (e) {
      toast.error(e?.response?.status === 404 ? "Couldn't reach memory store. Pull to refresh and try again." : "Couldn't save. Try again.");
    }
  };

  const removeMemory = async (id) => {
    try {
      await api.delete(`/companion/memories/${id}`);
      setMemories(memories.filter((m) => m.id !== id));
    } catch { toast.error("Couldn't remove. Try again."); }
  };

  const togglePin = async (mem) => {
    try {
      const { data } = await api.patch(`/companion/memories/${mem.id}`, { pinned: !mem.pinned });
      setMemories(memories.map(m => m.id === mem.id ? { ...m, pinned: data.pinned ?? !mem.pinned } : m));
    } catch { toast.error("Couldn't update."); }
  };

  const rememberMessage = async (msg) => {
    try {
      await api.post("/companion/memories", { content: msg.content, category: "story" });
      const mm = await api.get("/companion/memories");
      setMemories(mm.data);
      toast.success("Saved as memory");
    } catch { toast.error("Couldn't save."); }
  };

  const clearChat = async () => {
    if (!window.confirm("Clear all messages? Memories will stay.")) return;
    try {
      await api.delete("/companion/messages");
      setMessages([]);
    } catch { toast.error("Couldn't clear."); }
  };

  const lockNow = () => {
    clearUnlock();
    setUnlocked(false);
    setMessages([]);
    setMemories([]);
    toast.success("Locked");
  };

  if (!companion) return <Container><p className="text-[#6B7270]">Loading…</p></Container>;

  // PIN gate: pinEnabled has to be checked, and unlocked false
  if (pinEnabled && !unlocked) {
    return (
      <Container className="!py-8">
        <PinGate companionName={companion.name} onUnlock={() => setUnlocked(true)}/>
      </Container>
    );
  }

  const persona = PERSONAS.find(p => p.key === companion.persona) || PERSONAS[0];

  return (
    <Container className="!py-8">
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6 h-[calc(100vh-4rem)]">
        {/* Chat panel */}
        <div className="flex flex-col bg-white rounded-3xl border border-sand overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-sand bg-[#FDFBF7]">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-full bg-gradient-to-br from-[#59745D] to-[#A3897C] flex items-center justify-center">
                <span className="font-serif text-white text-xl">{companion.name?.[0]?.toUpperCase() || "N"}</span>
              </div>
              <div>
                <p className="font-serif text-2xl text-[#2D312E] leading-none">{companion.name}</p>
                <p className="text-xs uppercase tracking-widest text-[#C27A62] mt-1" data-testid="persona-label">
                  {persona.label} mode
                  {messages.length > 0 && (
                    <span className="text-[#9A9F9D] normal-case tracking-normal ml-2" title={`Your chat history is saved on this device's database. ${companion.name} uses recent messages and saved memories to recall what you've discussed.`}>
                      · {messages.length} msg{messages.length === 1 ? "" : "s"} kept
                    </span>
                  )}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button size="sm" variant="ghost" onClick={() => setMemoryLaneOpen(true)} className="rounded-full text-[#6B7270]" data-testid="open-memory-lane-btn" title="Search past chats">
                <Search size={15} strokeWidth={1.5} className="mr-1"/> <span className="hidden sm:inline">Memory Lane</span>
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setMemoryOpen(true)} className="rounded-full text-[#6B7270]" data-testid="open-memories-btn">
                <Brain size={15} strokeWidth={1.5} className="mr-1"/> Memories ({memories.length})
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setSettingsOpen(true)} className="rounded-full text-[#6B7270]" data-testid="open-settings-btn">
                <Settings size={15} strokeWidth={1.5}/>
              </Button>
              {pinEnabled && (
                <Button size="sm" variant="ghost" onClick={lockNow} className="rounded-full text-[#6B7270] hover:text-[#59745D]" data-testid="lock-now-btn" title="Lock this conversation">
                  <Lock size={15} strokeWidth={1.5}/>
                </Button>
              )}
              {messages.length > 0 && (
                <Button size="sm" variant="ghost" onClick={clearChat} className="rounded-full text-[#9A9F9D] hover:text-[#B85C50]" data-testid="clear-chat-btn">
                  <Trash2 size={14} strokeWidth={1.5}/>
                </Button>
              )}
            </div>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-5" data-testid="chat-thread">
            {messages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto">
                <div className="w-16 h-16 rounded-full bg-[#F4F1EA] flex items-center justify-center mb-4">
                  <Sparkles size={24} strokeWidth={1.5} className="text-[#C27A62]"/>
                </div>
                <h2 className="font-serif text-3xl text-[#2D312E] leading-tight">Say hello to {companion.name}.</h2>
                <p className="text-[#6B7270] mt-3 leading-relaxed">
                  Share a story, a thought, a question. {companion.name} listens, remembers, and grows with you.
                </p>
              </div>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`} data-testid={`msg-${m.role}`}>
                <div className="max-w-[78%] flex flex-col items-stretch gap-1">
                  <div className={`group relative rounded-3xl px-5 py-3 ${
                    m.role === "user"
                      ? "bg-[#59745D] text-white rounded-br-md self-end"
                      : "bg-[#F4F1EA] text-[#2D312E] rounded-bl-md self-start"
                  }`}>
                    <p className="leading-relaxed whitespace-pre-wrap">{m.content}</p>
                    {m.role === "user" && m.id !== "tmp-u" && (
                      <button
                        onClick={() => rememberMessage(m)}
                        className="absolute -bottom-7 right-2 opacity-0 group-hover:opacity-100 transition-opacity text-[10px] uppercase tracking-widest text-[#A3897C] hover:text-[#C27A62]"
                        data-testid={`remember-${m.id}`}
                      >
                        <Star size={11} strokeWidth={1.5} className="inline mr-1"/> remember this
                      </button>
                    )}
                  </div>
                  {m.role === "assistant" && (m.actions || []).length > 0 && (
                    <ActionChips
                      message={m}
                      onMessageUpdate={(updated) => setMessages(prev => prev.map(x => x.id === updated.id ? updated : x))}
                    />
                  )}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="bg-[#F4F1EA] rounded-3xl rounded-bl-md px-5 py-3">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-[#A3897C] rounded-full animate-bounce" style={{animationDelay: '0ms'}}></span>
                    <span className="w-2 h-2 bg-[#A3897C] rounded-full animate-bounce" style={{animationDelay: '150ms'}}></span>
                    <span className="w-2 h-2 bg-[#A3897C] rounded-full animate-bounce" style={{animationDelay: '300ms'}}></span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="border-t border-sand p-4 bg-[#FDFBF7]">
            <div className="flex items-end gap-2">
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
                }}
                placeholder={`Talk to ${companion.name}…`}
                rows={1}
                className="resize-none rounded-3xl bg-white border-sand min-h-[44px] max-h-32"
                data-testid="chat-input"
              />
              <Button onClick={send} disabled={sending || !input.trim()} className="rounded-full bg-[#59745D] hover:bg-[#4A604D] h-11 w-11 p-0" data-testid="send-btn">
                <Send size={16} strokeWidth={1.5}/>
              </Button>
            </div>
          </div>
        </div>

        <CompanionSidePanel
          companion={companion}
          memories={memories}
          onPersonaChange={(key) => updateCompanion({ persona: key })}
          onOpenMemories={() => setMemoryOpen(true)}
        />
      </div>

      <CompanionSettings
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        companion={companion}
        setCompanion={setCompanion}
        onUpdate={updateCompanion}
        pinEnabled={pinEnabled}
        setPinEnabled={setPinEnabled}
      />

      <MemoriesDialog
        open={memoryOpen}
        onOpenChange={setMemoryOpen}
        companionName={companion.name}
        memories={memories}
        newMem={newMem}
        setNewMem={setNewMem}
        onAdd={addMemory}
        onRemove={removeMemory}
        onTogglePin={togglePin}
      />

      <MemoryLaneDialog
        open={memoryLaneOpen}
        onOpenChange={setMemoryLaneOpen}
        companionName={companion.name}
      />
    </Container>
  );
}
