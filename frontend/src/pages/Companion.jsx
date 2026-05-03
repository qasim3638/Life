import React, { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { Container, Card, Eyebrow } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Send, Sparkles, Brain, Trash2, Plus, Settings, Star, BookOpen } from "lucide-react";
import { toast } from "sonner";

const PERSONAS = [
  { key: "friend", label: "Friend", desc: "Warm, present, curious" },
  { key: "secretary", label: "Secretary", desc: "Organised & efficient" },
  { key: "manager", label: "Manager", desc: "Direct & accountable" },
  { key: "coach", label: "Coach", desc: "Reflective & growth-minded" },
];

const CATEGORIES = ["general", "family", "work", "health", "dream", "story"];

export default function Companion() {
  const [companion, setCompanion] = useState(null);
  const [messages, setMessages] = useState([]);
  const [memories, setMemories] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [newMem, setNewMem] = useState({ content: "", category: "general" });
  const scrollRef = useRef(null);

  const load = async () => {
    const [c, m, mm] = await Promise.all([
      api.get("/companion"),
      api.get("/companion/messages"),
      api.get("/companion/memories"),
    ]);
    setCompanion(c.data);
    setMessages(m.data);
    setMemories(mm.data);
  };

  useEffect(() => { load(); }, []);

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
      const { data } = await api.post("/companion/chat", { message: text });
      // Reload messages from server (cleaner than guess-merging)
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
    await api.post("/companion/memories", newMem);
    setNewMem({ content: "", category: "general" });
    const mm = await api.get("/companion/memories");
    setMemories(mm.data);
    toast.success("Saved to memory");
  };

  const removeMemory = async (id) => {
    await api.delete(`/companion/memories/${id}`);
    setMemories(memories.filter((m) => m.id !== id));
  };

  const rememberMessage = async (msg) => {
    await api.post("/companion/memories", { content: msg.content, category: "story" });
    const mm = await api.get("/companion/memories");
    setMemories(mm.data);
    toast.success("Saved as memory");
  };

  const clearChat = async () => {
    if (!window.confirm("Clear all messages? Memories will stay.")) return;
    await api.delete("/companion/messages");
    setMessages([]);
  };

  if (!companion) return <Container><p className="text-[#6B7270]">Loading…</p></Container>;

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
                <p className="text-xs uppercase tracking-widest text-[#C27A62] mt-1">{persona.label} mode</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button size="sm" variant="ghost" onClick={() => setMemoryOpen(true)} className="rounded-full text-[#6B7270]" data-testid="open-memories-btn">
                <Brain size={15} strokeWidth={1.5} className="mr-1"/> Memories ({memories.length})
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setSettingsOpen(true)} className="rounded-full text-[#6B7270]" data-testid="open-settings-btn">
                <Settings size={15} strokeWidth={1.5}/>
              </Button>
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
                <div className={`group relative max-w-[78%] rounded-3xl px-5 py-3 ${
                  m.role === "user"
                    ? "bg-[#59745D] text-white rounded-br-md"
                    : "bg-[#F4F1EA] text-[#2D312E] rounded-bl-md"
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

        {/* Side panel — persona quick switch */}
        <div className="hidden lg:flex flex-col gap-4">
          <Card>
            <Eyebrow>Mode</Eyebrow>
            <p className="font-serif text-xl text-[#2D312E] mt-1 mb-3">How should {companion.name} show up?</p>
            <div className="space-y-2">
              {PERSONAS.map(p => (
                <button
                  key={p.key}
                  onClick={() => updateCompanion({ persona: p.key })}
                  className={`w-full text-left px-4 py-3 rounded-2xl transition-colors ${
                    companion.persona === p.key
                      ? "bg-[#59745D] text-white"
                      : "bg-[#F4F1EA] text-[#2D312E] hover:bg-sand"
                  }`}
                  data-testid={`persona-${p.key}`}
                >
                  <p className="font-medium">{p.label}</p>
                  <p className={`text-xs mt-0.5 ${companion.persona === p.key ? "text-white/80" : "text-[#6B7270]"}`}>
                    {p.desc}
                  </p>
                </button>
              ))}
            </div>
          </Card>
          <Card>
            <Eyebrow>Recent memories</Eyebrow>
            {memories.length === 0 ? (
              <p className="text-sm text-[#9A9F9D] mt-2 italic">Nothing saved yet. Use the star on your messages or add manually.</p>
            ) : (
              <ul className="mt-3 space-y-2 max-h-64 overflow-y-auto">
                {memories.slice(0, 6).map(m => (
                  <li key={m.id} className="text-sm text-[#2D312E] bg-[#F4F1EA] rounded-xl px-3 py-2">
                    <span className="text-[10px] uppercase tracking-widest text-[#C27A62] block">{m.category}</span>
                    {m.content}
                  </li>
                ))}
              </ul>
            )}
            <Button variant="ghost" onClick={() => setMemoryOpen(true)} className="rounded-full text-[#59745D] mt-3 w-full" data-testid="manage-memories-btn">
              <BookOpen size={14} strokeWidth={1.5} className="mr-1"/> Manage memories
            </Button>
          </Card>
        </div>
      </div>

      {/* Settings dialog */}
      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent className="rounded-3xl">
          <DialogHeader><DialogTitle className="font-serif text-2xl">Companion settings</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div>
              <p className="text-xs uppercase tracking-wider text-[#9A9F9D] mb-1">Their name</p>
              <Input
                value={companion.name}
                onChange={(e) => setCompanion({ ...companion, name: e.target.value })}
                onBlur={(e) => updateCompanion({ name: e.target.value })}
                data-testid="settings-name"
              />
            </div>
            <div>
              <p className="text-xs uppercase tracking-wider text-[#9A9F9D] mb-1">What they call you</p>
              <Input
                value={companion.user_name}
                onChange={(e) => setCompanion({ ...companion, user_name: e.target.value })}
                onBlur={(e) => updateCompanion({ user_name: e.target.value })}
                data-testid="settings-user-name"
              />
            </div>
            <div>
              <p className="text-xs uppercase tracking-wider text-[#9A9F9D] mb-1">Persona</p>
              <Select value={companion.persona} onValueChange={(v) => updateCompanion({ persona: v })}>
                <SelectTrigger data-testid="settings-persona"><SelectValue/></SelectTrigger>
                <SelectContent>
                  {PERSONAS.map(p => <SelectItem key={p.key} value={p.key}>{p.label} — {p.desc}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Memories drawer */}
      <Dialog open={memoryOpen} onOpenChange={setMemoryOpen}>
        <DialogContent className="rounded-3xl max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-serif text-2xl">Things {companion.name} remembers</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="bg-[#F4F1EA] rounded-2xl p-4">
              <p className="text-xs uppercase tracking-widest text-[#9A9F9D] mb-2">Add a memory</p>
              <Textarea
                value={newMem.content}
                onChange={(e) => setNewMem({ ...newMem, content: e.target.value })}
                placeholder="Tell them something they should always remember…"
                rows={3}
                className="bg-white"
                data-testid="memory-content-input"
              />
              <div className="flex gap-2 mt-3">
                <Select value={newMem.category} onValueChange={(v) => setNewMem({ ...newMem, category: v })}>
                  <SelectTrigger className="bg-white" data-testid="memory-category-select"><SelectValue/></SelectTrigger>
                  <SelectContent>
                    {CATEGORIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Button onClick={addMemory} className="rounded-full bg-[#59745D]" data-testid="add-memory-btn">
                  <Plus size={14} className="mr-1"/> Save
                </Button>
              </div>
            </div>

            <div>
              <p className="text-xs uppercase tracking-widest text-[#9A9F9D] mb-2">Saved ({memories.length})</p>
              {memories.length === 0 && <p className="text-sm text-[#9A9F9D] italic">Empty.</p>}
              <div className="space-y-2">
                {memories.map(m => (
                  <div key={m.id} className="flex items-start gap-3 bg-white border border-sand rounded-2xl px-4 py-3" data-testid={`memory-${m.id}`}>
                    <div className="flex-1">
                      <span className="text-[10px] uppercase tracking-widest text-[#C27A62]">{m.category}</span>
                      <p className="text-sm text-[#2D312E] leading-relaxed mt-1">{m.content}</p>
                    </div>
                    <button onClick={() => removeMemory(m.id)} className="text-[#9A9F9D] hover:text-[#B85C50]"><Trash2 size={14} strokeWidth={1.5}/></button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </Container>
  );
}
