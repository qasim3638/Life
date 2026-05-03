import React, { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Plus, Youtube } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";

/**
 * Generic "Add your own YouTube" dialog used by Motivation (kind=podcast) and Meditate (kind=meditation).
 * onAdded is called after a successful POST so the parent can refresh its list.
 */
export default function AddYouTubeDialog({ kind, categories, onAdded, trigger }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    title: "",
    url_or_id: "",
    category: categories[0],
    duration: "",
    host: "",
    description: "",
  });

  const reset = () => setForm({
    title: "", url_or_id: "", category: categories[0],
    duration: "", host: "", description: "",
  });

  const submit = async () => {
    if (!form.title.trim()) return toast.error("Add a title");
    if (!form.url_or_id.trim()) return toast.error("Paste a YouTube URL");
    setSaving(true);
    try {
      const endpoint = kind === "podcast" ? "/podcasts" : "/meditations";
      const payload = kind === "podcast"
        ? { title: form.title, url_or_id: form.url_or_id, host: form.host, category: form.category, duration: form.duration }
        : { title: form.title, url_or_id: form.url_or_id, category: form.category, duration: form.duration, description: form.description };
      await api.post(endpoint, payload);
      toast.success(kind === "podcast" ? "Added to your library" : "Saved to your meditations");
      setOpen(false);
      reset();
      onAdded?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Couldn't save — check the YouTube URL");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {trigger ? (
        <span onClick={() => setOpen(true)}>{trigger}</span>
      ) : (
        <Button
          onClick={() => setOpen(true)}
          className="rounded-full bg-[#59745D] hover:bg-[#4A604D]"
          data-testid={`add-${kind}-btn`}
        >
          <Plus size={15} strokeWidth={1.5} className="mr-1"/> Add your own
        </Button>
      )}
      <DialogContent className="rounded-3xl max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-serif text-2xl flex items-center gap-2">
            <Youtube size={18} strokeWidth={1.5} className="text-[#C27A62]"/>
            Add a YouTube {kind}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 mt-2">
          <Input
            placeholder="Title"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            data-testid={`add-${kind}-title`}
          />
          <Input
            placeholder="YouTube URL (e.g. https://youtu.be/xxx) or 11-char video ID"
            value={form.url_or_id}
            onChange={(e) => setForm({ ...form, url_or_id: e.target.value })}
            data-testid={`add-${kind}-url`}
          />
          <div className="grid grid-cols-2 gap-3">
            <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
              <SelectTrigger data-testid={`add-${kind}-category`}><SelectValue/></SelectTrigger>
              <SelectContent>
                {categories.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
              </SelectContent>
            </Select>
            <Input
              placeholder="Duration (e.g. 10 min)"
              value={form.duration}
              onChange={(e) => setForm({ ...form, duration: e.target.value })}
              data-testid={`add-${kind}-duration`}
            />
          </div>
          {kind === "podcast" ? (
            <Input
              placeholder="Host / speaker (optional)"
              value={form.host}
              onChange={(e) => setForm({ ...form, host: e.target.value })}
              data-testid={`add-${kind}-host`}
            />
          ) : (
            <Textarea
              placeholder="Short description (optional)"
              rows={2}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              data-testid={`add-${kind}-description`}
            />
          )}
          <Button
            onClick={submit}
            disabled={saving}
            className="w-full rounded-full bg-[#59745D] hover:bg-[#4A604D]"
            data-testid={`add-${kind}-submit`}
          >
            {saving ? "Saving…" : "Save to library"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
