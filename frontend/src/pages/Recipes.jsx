import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Container, Card, Eyebrow, PageHeader } from "../components/Layout";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Sparkles, Clock, Flame, Wheat, Beef, Plus } from "lucide-react";
import { toast } from "sonner";

const CUISINES = ["All", "Pakistani", "Indian", "Arab", "Mediterranean"];
const MEALS = ["All", "Breakfast", "Lunch", "Dinner", "Snack"];

export default function Recipes() {
  const [recipes, setRecipes] = useState([]);
  const [cuisine, setCuisine] = useState("All");
  const [meal, setMeal] = useState("All");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);
  const [aiOpen, setAiOpen] = useState(false);
  const [aiText, setAiText] = useState("");
  const [aiCtx, setAiCtx] = useState("something high-protein for tonight");
  const [aiLoading, setAiLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [newRecipe, setNewRecipe] = useState({
    title: "", cuisine: "Pakistani", meal_type: "Dinner",
    prep_time: 30, servings: 2, calories: 400, protein: 35, carbs: 10, fat: 20,
    ingredients: "", instructions: "", image: "",
  });

  const load = async () => {
    const { data } = await api.get("/recipes");
    setRecipes(data);
  };
  useEffect(() => { load(); }, []);

  const filtered = recipes.filter(r =>
    (cuisine === "All" || r.cuisine === cuisine) &&
    (meal === "All" || r.meal_type === meal) &&
    (!query || r.title.toLowerCase().includes(query.toLowerCase()))
  );

  const askAI = async () => {
    setAiLoading(true);
    try {
      const { data } = await api.post("/ai/meal-suggestion", { prompt: aiCtx });
      setAiText(data.text);
    } catch { toast.error("AI is resting"); }
    finally { setAiLoading(false); }
  };

  const saveRecipe = async () => {
    if (!newRecipe.title.trim() || !newRecipe.ingredients.trim()) {
      return toast.error("Title and ingredients are required");
    }
    const payload = {
      ...newRecipe,
      ingredients: newRecipe.ingredients.split("\n").map(s => s.trim()).filter(Boolean),
      instructions: newRecipe.instructions.split("\n").map(s => s.trim()).filter(Boolean),
      image: newRecipe.image || "https://images.unsplash.com/photo-1659275798977-6eee03f687a2",
      tags: [],
    };
    try {
      await api.post("/recipes", payload);
      toast.success("Recipe saved");
      setCreateOpen(false);
      setNewRecipe({
        title: "", cuisine: "Pakistani", meal_type: "Dinner",
        prep_time: 30, servings: 2, calories: 400, protein: 35, carbs: 10, fat: 20,
        ingredients: "", instructions: "", image: "",
      });
      load();
    } catch { toast.error("Couldn't save"); }
  };

  return (
    <Container>
      <PageHeader
        eyebrow="Nourishment"
        title="Food that loves you back."
        subtitle="High protein, lower carbs, zero pork — rooted in Pakistani, Indian, and Arab traditions."
        image="https://images.unsplash.com/photo-1659275798977-6eee03f687a2"
      />

      <div className="flex flex-wrap items-center gap-3 mb-8">
        <Input placeholder="Search recipes…" value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="max-w-xs rounded-full" data-testid="recipe-search"
        />
        <Select value={cuisine} onValueChange={setCuisine}>
          <SelectTrigger className="w-[170px] rounded-full" data-testid="cuisine-filter"><SelectValue /></SelectTrigger>
          <SelectContent>{CUISINES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={meal} onValueChange={setMeal}>
          <SelectTrigger className="w-[150px] rounded-full" data-testid="meal-filter"><SelectValue /></SelectTrigger>
          <SelectContent>{MEALS.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
        </Select>
        <Button
          variant="outline"
          onClick={() => setAiOpen(true)}
          className="rounded-full border-[#C27A62] text-[#C27A62] hover:bg-[#C27A62] hover:text-white ml-auto"
          data-testid="ai-meal-btn"
        >
          <Sparkles size={15} strokeWidth={1.5} className="mr-1" /> Ask AI chef
        </Button>
        <Button
          onClick={() => setCreateOpen(true)}
          className="rounded-full bg-[#59745D] hover:bg-[#4A604D]"
          data-testid="add-recipe-btn"
        >
          <Plus size={15} strokeWidth={1.5} className="mr-1" /> Add recipe
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {filtered.map(r => (
          <Card key={r.id}
            data-testid={`recipe-${r.id}`}
            className="p-0 overflow-hidden cursor-pointer hover:-translate-y-1"
            onClick={() => setSelected(r)}
          >
            <div className="h-44 bg-cover bg-center relative" style={{ backgroundImage: `url(${r.image})` }}>
              <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent" />
              <div className="absolute top-3 left-3 px-3 py-1 rounded-full bg-white/90 text-[10px] uppercase tracking-wider text-[#2D312E]">
                {r.cuisine}
              </div>
              <div className="absolute bottom-3 left-3 right-3">
                <h3 className="font-serif text-white text-2xl leading-tight">{r.title}</h3>
              </div>
            </div>
            <div className="p-5">
              <div className="flex items-center gap-4 text-xs text-[#6B7270]">
                <span className="flex items-center gap-1"><Clock size={13} strokeWidth={1.5} /> {r.prep_time}m</span>
                <span className="flex items-center gap-1"><Flame size={13} strokeWidth={1.5} /> {r.calories} kcal</span>
                <span className="flex items-center gap-1"><Beef size={13} strokeWidth={1.5} /> {r.protein}g P</span>
                <span className="flex items-center gap-1"><Wheat size={13} strokeWidth={1.5} /> {r.carbs}g C</span>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {filtered.length === 0 && (
        <p className="text-center text-[#6B7270] py-16">No recipes match. Try a different filter.</p>
      )}

      {/* Recipe detail */}
      <Dialog open={!!selected} onOpenChange={() => setSelected(null)}>
        <DialogContent className="rounded-3xl max-w-2xl max-h-[90vh] overflow-y-auto p-0">
          {selected && (
            <>
              <div className="h-56 bg-cover bg-center relative rounded-t-3xl" style={{ backgroundImage: `url(${selected.image})` }}>
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent rounded-t-3xl" />
                <div className="absolute bottom-5 left-6 right-6">
                  <p className="text-xs uppercase tracking-[0.3em] text-white/80">{selected.cuisine} · {selected.meal_type}</p>
                  <h2 className="font-serif text-3xl text-white mt-1">{selected.title}</h2>
                </div>
              </div>
              <div className="p-7">
                <div className="grid grid-cols-4 gap-2 text-center mb-6 text-xs">
                  <div><p className="font-serif text-2xl text-[#59745D]">{selected.calories}</p><p className="text-[#9A9F9D] mt-0.5">kcal</p></div>
                  <div><p className="font-serif text-2xl text-[#59745D]">{selected.protein}g</p><p className="text-[#9A9F9D] mt-0.5">protein</p></div>
                  <div><p className="font-serif text-2xl text-[#C27A62]">{selected.carbs}g</p><p className="text-[#9A9F9D] mt-0.5">carbs</p></div>
                  <div><p className="font-serif text-2xl text-[#A3897C]">{selected.fat}g</p><p className="text-[#9A9F9D] mt-0.5">fat</p></div>
                </div>
                <Eyebrow>Ingredients</Eyebrow>
                <ul className="space-y-1 mt-2 text-sm text-[#2D312E]">
                  {selected.ingredients.map((i, idx) => <li key={idx}>· {i}</li>)}
                </ul>
                <Eyebrow>Method</Eyebrow>
                <ol className="space-y-2 mt-2 text-sm text-[#2D312E]">
                  {selected.instructions.map((s, idx) => (
                    <li key={idx} className="flex gap-3"><span className="font-serif text-[#C27A62]">{idx + 1}.</span><span>{s}</span></li>
                  ))}
                </ol>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={aiOpen} onOpenChange={setAiOpen}>
        <DialogContent className="rounded-3xl">
          <DialogHeader><DialogTitle className="font-serif text-2xl">AI chef</DialogTitle></DialogHeader>
          <Input value={aiCtx} onChange={(e) => setAiCtx(e.target.value)} placeholder="Context (ingredients on hand, mood…)" data-testid="ai-meal-context"/>
          <Button onClick={askAI} disabled={aiLoading} className="rounded-full bg-[#C27A62] hover:bg-[#A3897C]" data-testid="ai-meal-generate">
            {aiLoading ? "Simmering…" : "Suggest a meal"}
          </Button>
          {aiText && <div className="bg-[#F4F1EA] rounded-2xl p-5 whitespace-pre-wrap text-sm text-[#2D312E] leading-relaxed">{aiText}</div>}
        </DialogContent>
      </Dialog>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="rounded-3xl max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-serif text-2xl">Save a recipe</DialogTitle></DialogHeader>
          <div className="space-y-3 mt-2">
            <Input placeholder="Recipe title" value={newRecipe.title}
              onChange={(e) => setNewRecipe({ ...newRecipe, title: e.target.value })}
              data-testid="new-recipe-title"/>
            <Input placeholder="Image URL (optional)" value={newRecipe.image}
              onChange={(e) => setNewRecipe({ ...newRecipe, image: e.target.value })}
              data-testid="new-recipe-image"/>
            <div className="grid grid-cols-2 gap-3">
              <Select value={newRecipe.cuisine} onValueChange={(v) => setNewRecipe({ ...newRecipe, cuisine: v })}>
                <SelectTrigger data-testid="new-recipe-cuisine"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["Pakistani", "Indian", "Arab", "Mediterranean", "Other"].map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={newRecipe.meal_type} onValueChange={(v) => setNewRecipe({ ...newRecipe, meal_type: v })}>
                <SelectTrigger data-testid="new-recipe-meal"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["Breakfast", "Lunch", "Dinner", "Snack"].map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input type="number" placeholder="Prep (min)" value={newRecipe.prep_time}
                onChange={(e) => setNewRecipe({ ...newRecipe, prep_time: parseInt(e.target.value) })} />
              <Input type="number" placeholder="Servings" value={newRecipe.servings}
                onChange={(e) => setNewRecipe({ ...newRecipe, servings: parseInt(e.target.value) })} />
            </div>
            <div className="grid grid-cols-4 gap-2">
              <Input type="number" placeholder="kcal" value={newRecipe.calories}
                onChange={(e) => setNewRecipe({ ...newRecipe, calories: parseInt(e.target.value) })} />
              <Input type="number" placeholder="P(g)" value={newRecipe.protein}
                onChange={(e) => setNewRecipe({ ...newRecipe, protein: parseInt(e.target.value) })} />
              <Input type="number" placeholder="C(g)" value={newRecipe.carbs}
                onChange={(e) => setNewRecipe({ ...newRecipe, carbs: parseInt(e.target.value) })} />
              <Input type="number" placeholder="F(g)" value={newRecipe.fat}
                onChange={(e) => setNewRecipe({ ...newRecipe, fat: parseInt(e.target.value) })} />
            </div>
            <Textarea placeholder="Ingredients (one per line)" rows={5}
              value={newRecipe.ingredients}
              onChange={(e) => setNewRecipe({ ...newRecipe, ingredients: e.target.value })}
              data-testid="new-recipe-ingredients"/>
            <Textarea placeholder="Method steps (one per line)" rows={4}
              value={newRecipe.instructions}
              onChange={(e) => setNewRecipe({ ...newRecipe, instructions: e.target.value })}
              data-testid="new-recipe-instructions"/>
            <Button onClick={saveRecipe} className="w-full rounded-full bg-[#59745D]" data-testid="save-new-recipe-btn">Save recipe</Button>
          </div>
        </DialogContent>
      </Dialog>
    </Container>
  );
}
