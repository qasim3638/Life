"""Recipes."""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from db import db
from models import Recipe, RecipeCreate

router = APIRouter()


@router.get("/recipes", response_model=List[Recipe])
async def list_recipes(cuisine: Optional[str] = None, meal_type: Optional[str] = None):
    q: dict = {}
    if cuisine:
        q["cuisine"] = cuisine
    if meal_type:
        q["meal_type"] = meal_type
    return await db.recipes.find(q, {"_id": 0}).to_list(500)


@router.get("/recipes/{recipe_id}", response_model=Recipe)
async def get_recipe(recipe_id: str):
    item = await db.recipes.find_one({"id": recipe_id}, {"_id": 0})
    if not item:
        raise HTTPException(404, "Recipe not found")
    return item


@router.post("/recipes", response_model=Recipe)
async def create_recipe(payload: RecipeCreate):
    r = Recipe(**payload.model_dump(), is_custom=True)
    await db.recipes.insert_one(r.model_dump())
    return r


@router.delete("/recipes/{recipe_id}")
async def delete_recipe(recipe_id: str):
    await db.recipes.delete_one({"id": recipe_id, "is_custom": True})
    return {"ok": True}
