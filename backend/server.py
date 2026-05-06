"""Life Blueprint API — entry point."""
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
import os
import logging

from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# imports below need env loaded
from db import client, db  # noqa: E402
from models import Recipe, new_id  # noqa: E402
from seed_data import (  # noqa: E402
    RECIPES_SEED, QUOTES_SEED, PODCASTS_SEED, MEDITATIONS_SEED, AFFIRMATIONS_SEED,
)
from routes import (  # noqa: E402
    workouts, recipes, journal, events, life_goals, content,
    day_plans, streaks, ai_endpoints, companion, family, audio, self_profile,
    focus, sobriety, echo, sunday_review, uploads, sanctuary, companion_alerts,
    voice, auth,
)
from auth_utils import decode_token, seed_auth_user  # noqa: E402
from audio_seed import (  # noqa: E402
    WISDOM_STORIES_SEED, SLEEP_STORIES_SEED, MEDITATION_MUSIC_SEED,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        if await db.recipes.count_documents({"is_custom": False}) == 0:
            for r in RECIPES_SEED:
                doc = Recipe(**r, is_custom=False).model_dump()
                await db.recipes.insert_one(doc)
        if await db.quotes.count_documents({}) == 0:
            for q in QUOTES_SEED:
                await db.quotes.insert_one({"id": new_id(), **q})
        if await db.podcasts.count_documents({}) == 0:
            for p in PODCASTS_SEED:
                await db.podcasts.insert_one({"id": new_id(), **p})
        if await db.meditations.count_documents({}) == 0:
            for m in MEDITATIONS_SEED:
                await db.meditations.insert_one({"id": new_id(), **m})
        if await db.affirmations.count_documents({}) == 0:
            for a in AFFIRMATIONS_SEED:
                await db.affirmations.insert_one({"id": new_id(), "text": a})
        if await db.audio_library.count_documents({}) == 0:
            for item in WISDOM_STORIES_SEED + SLEEP_STORIES_SEED + MEDITATION_MUSIC_SEED:
                await db.audio_library.insert_one({"id": new_id(), **item})
        await sanctuary.seed_if_empty()
        await seed_auth_user()
        logger.info("Seed data ready.")
    except Exception as e:
        logger.error(f"Seeding error: {e}")
    yield
    client.close()


app = FastAPI(title="Life Blueprint API", lifespan=lifespan)


# /api root health
api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"message": "Life Blueprint API", "status": "ok"}


api_router.include_router(workouts.router)
api_router.include_router(recipes.router)
api_router.include_router(journal.router)
api_router.include_router(events.router)
api_router.include_router(life_goals.router)
api_router.include_router(content.router)
api_router.include_router(day_plans.router)
api_router.include_router(streaks.router)
api_router.include_router(ai_endpoints.router)
api_router.include_router(companion.router)
api_router.include_router(family.router)
api_router.include_router(audio.router)
api_router.include_router(self_profile.router)
api_router.include_router(focus.router)
api_router.include_router(sobriety.router)
api_router.include_router(echo.router)
api_router.include_router(sunday_review.router)
api_router.include_router(uploads.router)
api_router.include_router(sanctuary.router)
api_router.include_router(companion_alerts.router)
api_router.include_router(voice.router)
api_router.include_router(auth.router)

app.include_router(api_router)


# ---- Auth middleware ----
# Require Bearer token on every /api/* route except auth endpoints and static
# uploads. Kicks in only if AUTH_EMAIL + AUTH_PASSWORD env vars are set
# (so the dev/preview environment without those vars stays wide-open).
@app.middleware("http")
async def auth_middleware(request, call_next):
    if not (os.environ.get("AUTH_EMAIL") and os.environ.get("AUTH_PASSWORD")):
        return await call_next(request)
    path = request.url.path
    if (
        not path.startswith("/api/")
        or path == "/api/"
        or path.startswith("/api/auth/")
        or path.startswith("/api/uploads/")
        or request.method == "OPTIONS"
    ):
        return await call_next(request)
    auth_h = request.headers.get("Authorization", "")
    token = auth_h[7:] if auth_h.startswith("Bearer ") else None
    if not token or not decode_token(token):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    return await call_next(request)

# Serve uploaded files at /api/uploads/*
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
