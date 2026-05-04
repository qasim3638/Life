import React, { useEffect, useState, useRef } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { api } from "../../lib/api";
import { Search, Quote, X } from "lucide-react";

const fmtDate = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" }) +
    " · " + d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
};

function highlight(text, q) {
  if (!q) return text;
  const idx = text.toLowerCase().indexOf(q.toLowerCase());
  if (idx < 0) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-[#F2D9A0] text-[#2D312E] rounded px-0.5">{text.slice(idx, idx + q.length)}</mark>
      {text.slice(idx + q.length)}
    </>
  );
}

export default function MemoryLaneDialog({ open, onOpenChange, companionName }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [touched, setTouched] = useState(false);
  const debounceRef = useRef(null);
  const inputRef = useRef(null);

  // Reset on close
  useEffect(() => {
    if (!open) {
      setQ("");
      setResults([]);
      setTouched(false);
    } else {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  // Debounced search
  useEffect(() => {
    if (!open) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) { setResults([]); setTouched(false); return; }
    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const { data } = await api.get(`/companion/messages/search`, { params: { q: q.trim() } });
        setResults(data || []);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
        setTouched(true);
      }
    }, 320);
    return () => clearTimeout(debounceRef.current);
  }, [q, open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-3xl max-w-3xl max-h-[85vh] overflow-hidden flex flex-col p-0">
        <DialogHeader className="px-6 pt-6 pb-3 border-b border-sand">
          <DialogTitle className="font-serif text-2xl text-[#2D312E]">Memory Lane</DialogTitle>
          <p className="text-sm text-[#6B7270] mt-1">
            Every word you and {companionName} have shared, searchable. Try a name, a place, a feeling.
          </p>
        </DialogHeader>

        <div className="px-6 py-4 border-b border-sand bg-[#FDFBF7]">
          <div className="relative">
            <Search size={16} strokeWidth={1.5} className="absolute left-4 top-1/2 -translate-y-1/2 text-[#9A9F9D]"/>
            <input
              ref={inputRef}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search past chats — e.g. Cumbria, gym, weed, mum…"
              className="w-full bg-white border border-sand rounded-full pl-10 pr-10 h-11 text-[#2D312E] focus:outline-none focus:border-[#59745D]"
              data-testid="memory-lane-search-input"
            />
            {q && (
              <button
                onClick={() => setQ("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full hover:bg-[#F4F1EA] flex items-center justify-center text-[#9A9F9D]"
                title="Clear"
              >
                <X size={14} strokeWidth={1.5}/>
              </button>
            )}
          </div>
          {q.trim() && (
            <p className="text-xs text-[#9A9F9D] mt-2">
              {loading ? "Searching…" : `${results.length} match${results.length === 1 ? "" : "es"}`}
            </p>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4" data-testid="memory-lane-results">
          {!q.trim() && (
            <Empty
              icon={<Quote size={28} strokeWidth={1.2}/>}
              title="Start typing"
              body={`Search across everything you and ${companionName} have ever talked about. Memories that mattered are still here.`}
            />
          )}
          {q.trim() && touched && !loading && results.length === 0 && (
            <Empty
              icon={<Search size={28} strokeWidth={1.2}/>}
              title="No matches"
              body={`No moments mention "${q}" yet. Try a shorter or different word.`}
            />
          )}
          {results.map((hit, i) => (
            <ResultCard key={i} hit={hit} q={q} companionName={companionName}/>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ResultCard({ hit, q, companionName }) {
  const { match, before, after } = hit;
  const speaker = (m) => m?.role === "user" ? "You" : companionName;
  return (
    <div className="rounded-2xl border border-sand bg-white p-4 hover:shadow-sm transition-shadow" data-testid="memory-lane-result-card">
      <p className="text-[10px] uppercase tracking-widest text-[#C27A62]">
        {fmtDate(match.created_at)}
      </p>
      {before && (
        <p className="text-xs text-[#9A9F9D] italic leading-relaxed mt-2">
          <span className="font-medium not-italic">{speaker(before)}:</span> {(before.content || "").slice(0, 140)}{(before.content || "").length > 140 ? "…" : ""}
        </p>
      )}
      <div className={`mt-2 rounded-xl px-3 py-2 ${match.role === "user" ? "bg-[#EDF1ED]" : "bg-[#F4F1EA]"}`}>
        <p className="text-[10px] uppercase tracking-widest text-[#6B7270]">{speaker(match)}</p>
        <p className="text-sm text-[#2D312E] leading-relaxed mt-1 whitespace-pre-wrap">
          {highlight(match.content || "", q)}
        </p>
      </div>
      {after && (
        <p className="text-xs text-[#9A9F9D] italic leading-relaxed mt-2">
          <span className="font-medium not-italic">{speaker(after)}:</span> {(after.content || "").slice(0, 140)}{(after.content || "").length > 140 ? "…" : ""}
        </p>
      )}
    </div>
  );
}

function Empty({ icon, title, body }) {
  return (
    <div className="text-center py-14 px-6 max-w-md mx-auto" data-testid="memory-lane-empty">
      <div className="w-14 h-14 rounded-full bg-[#F4F1EA] flex items-center justify-center mx-auto text-[#A3897C]">
        {icon}
      </div>
      <h3 className="font-serif text-2xl text-[#2D312E] mt-4">{title}</h3>
      <p className="text-sm text-[#6B7270] mt-2 leading-relaxed">{body}</p>
    </div>
  );
}
