"""Backend tests for AI recipe macro estimation (POST /api/ai/recipe-macros)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://mindful-40.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


class TestRecipeMacros:
    def test_real_ingredients_returns_ints(self, client):
        payload = {
            "title": "Grilled Chicken Yogurt Bowl",
            "ingredients": [
                "chicken breast 200g",
                "olive oil 1 tbsp",
                "lemon",
                "garlic",
                "greek yogurt 150g",
                "cucumber",
                "mint",
            ],
            "cuisine": "Mediterranean",
            "meal_type": "Dinner",
            "servings": 2,
        }
        r = client.post(f"{BASE_URL}/api/ai/recipe-macros", json=payload, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        for field in ("prep_time", "calories", "protein", "carbs", "fat"):
            assert field in data, f"missing {field} in {data}"
            assert isinstance(data[field], int), f"{field} not int: {data[field]!r}"
            assert data[field] > 0, f"{field} not > 0: {data[field]}"
        # reasonable ranges per serving
        assert 5 <= data["prep_time"] <= 180
        assert 100 <= data["calories"] <= 1500
        assert 5 <= data["protein"] <= 120
        assert 0 < data["carbs"] <= 200
        assert 0 < data["fat"] <= 120

    def test_empty_ingredients_returns_fallback(self, client):
        payload = {"title": "x", "ingredients": [], "servings": 2}
        r = client.post(f"{BASE_URL}/api/ai/recipe-macros", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # fallback: zeros + error message, no crash
        assert "error" in data
        for field in ("prep_time", "calories", "protein", "carbs", "fat"):
            assert field in data
            assert isinstance(data[field], int)
