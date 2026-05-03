"""Iter 11 tests: image upload endpoint + static serving + recipes regression."""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to frontend .env — but env should already be loaded
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")


# Tiny valid PNG (1x1 transparent)
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
    b"\x89\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    return s


# ---------- Upload endpoint ----------
class TestUploadEndpoint:
    def test_upload_png_success(self, session):
        files = {"file": ("test_iter11.png", PNG_BYTES, "image/png")}
        r = session.post(f"{BASE_URL}/api/upload/image", files=files, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "url" in data and "filename" in data
        assert data["url"].startswith("/api/uploads/")
        assert data["filename"].endswith(".png")
        # store url for next test
        TestUploadEndpoint._uploaded_url = data["url"]
        TestUploadEndpoint._uploaded_filename = data["filename"]

    def test_static_serve_uploaded_file(self, session):
        url = getattr(TestUploadEndpoint, "_uploaded_url", None)
        assert url, "previous upload test must have run"
        r = session.get(f"{BASE_URL}{url}", timeout=30)
        assert r.status_code == 200
        # should match bytes we sent
        assert r.content == PNG_BYTES
        ct = r.headers.get("content-type", "")
        assert "image" in ct or ct == "application/octet-stream"

    def test_upload_rejects_non_image_extension(self, session):
        files = {"file": ("evil.exe", b"MZ\x90\x00", "application/octet-stream")}
        r = session.post(f"{BASE_URL}/api/upload/image", files=files, timeout=30)
        assert r.status_code == 400
        assert "Unsupported" in r.text or "unsupported" in r.text.lower()

    def test_upload_rejects_oversized_file(self, session):
        big = b"\x00" * (5 * 1024 * 1024 + 100)
        files = {"file": ("big.png", big, "image/png")}
        r = session.post(f"{BASE_URL}/api/upload/image", files=files, timeout=60)
        assert r.status_code == 400
        assert "large" in r.text.lower() or "5mb" in r.text.lower()

    def test_upload_jpeg_success(self, session):
        # minimal JPEG bytes
        jpg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
        files = {"file": ("hi.jpg", jpg, "image/jpeg")}
        r = session.post(f"{BASE_URL}/api/upload/image", files=files, timeout=30)
        assert r.status_code == 200
        assert r.json()["filename"].endswith(".jpg")


# ---------- Recipe persistence regression ----------
class TestRecipeWithUpload:
    def test_create_recipe_with_uploaded_image(self, session):
        # upload first
        files = {"file": ("recipe_iter11.png", PNG_BYTES, "image/png")}
        u = session.post(f"{BASE_URL}/api/upload/image", files=files, timeout=30)
        assert u.status_code == 200
        upload_url = u.json()["url"]

        payload = {
            "title": "TEST_iter11_recipe",
            "cuisine": "Pakistani",
            "meal_type": "Dinner",
            "prep_time": 30, "servings": 2,
            "calories": 400, "protein": 35, "carbs": 10, "fat": 20,
            "ingredients": ["chicken", "yogurt"],
            "instructions": ["marinate", "grill"],
            "image": upload_url,
            "tags": [],
        }
        r = session.post(f"{BASE_URL}/api/recipes", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text
        created = r.json()
        assert created["image"] == upload_url
        assert created["title"] == "TEST_iter11_recipe"
        rid = created["id"]

        # GET list and verify it persists
        lst = session.get(f"{BASE_URL}/api/recipes", timeout=30)
        assert lst.status_code == 200
        found = next((x for x in lst.json() if x["id"] == rid), None)
        assert found is not None
        assert found["image"] == upload_url

        # cleanup
        d = session.delete(f"{BASE_URL}/api/recipes/{rid}", timeout=30)
        assert d.status_code in (200, 204)


# ---------- Health regression ----------
class TestHealth:
    def test_root(self, session):
        r = session.get(f"{BASE_URL}/api/", timeout=30)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"
