"""Sanctuary: calming nature content — sounds, scenery, stills.
Seeds on first boot; user can add/delete their own.
"""
import re
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db import db

router = APIRouter()
logger = logging.getLogger(__name__)


_YT_PATTERNS = [
    r"youtube\.com/watch\?v=([A-Za-z0-9_-]{11})",
    r"youtu\.be/([A-Za-z0-9_-]{11})",
    r"youtube\.com/embed/([A-Za-z0-9_-]{11})",
    r"^([A-Za-z0-9_-]{11})$",
]


def extract_youtube_id(value: str) -> str | None:
    v = (value or "").strip()
    for p in _YT_PATTERNS:
        m = re.search(p, v)
        if m:
            return m.group(1)
    return None


SOUNDS_SEED = [
    {"title": "Heavy Rain at Night", "youtube_id": "9QneqUhCVtU", "duration": "10 hours", "category": "Rain", "description": "Continuous heavy rain for sleep and deep focus."},
    {"title": "Gentle Rain — White Noise", "youtube_id": "BIcl7DrBcjg", "duration": "10 hours", "category": "Rain", "description": "Soft, even rain — a blanket over the mind."},
    {"title": "Rainforest Pitter-Patter", "youtube_id": "Pq-5vTJk38k", "duration": "10 hours", "category": "Rain", "description": "Rain on forest leaves."},
    {"title": "Foggy Spruce Forest Rain", "youtube_id": "8plwv25NYRo", "duration": "10 hours", "category": "Rain", "description": "Realistic rain drops from branches."},
    {"title": "Gentle Night Rain (3h)", "youtube_id": "q76bMs-NwRk", "duration": "3 hours", "category": "Rain", "description": "The Relaxed Guy — no music, no thunder."},
    {"title": "Rain on Leaves — Calm (8h)", "youtube_id": "yIQd2Ya0Ziw", "duration": "8 hours", "category": "Rain", "description": "Calm.com's official forest rainstorm."},
    {"title": "Rain Sounds for a Full Day (24h)", "youtube_id": "GqwagDvuWNk", "duration": "24 hours", "category": "Rain", "description": "Continuous heavy rain for deep sleep."},
    {"title": "Rain on Roof (10h)", "youtube_id": "mPZkdNFkNps", "duration": "10 hours", "category": "Rain", "description": "Warm tin-roof rain, cabin feel."},
    {"title": "Rain with Distant Thunder", "youtube_id": "ugxR1fXe-lg", "duration": "10 hours", "category": "Thunderstorm", "description": "Gentle storm from far away."},
    {"title": "Storm + Rain for Sleep", "youtube_id": "BSmYxnvUDHw", "duration": "10 hours", "category": "Thunderstorm", "description": "Deep rain with rolling thunder."},
    {"title": "Thunderstorm — 3 hours", "youtube_id": "nDq6TstdEi8", "duration": "3 hours", "category": "Thunderstorm", "description": "A real storm, end to end."},
    {"title": "Ocean Waves — 10 hours", "youtube_id": "bn9F19Hi1Lk", "duration": "10 hours", "category": "Ocean", "description": "Steady waves on the shore."},
    {"title": "Gentle Beach Waves", "youtube_id": "V1RPi2MYptM", "duration": "10 hours", "category": "Ocean", "description": "Lapping waves, wide open sky."},
    {"title": "Night Ocean Waves (10h)", "youtube_id": "iEy9BXGs2R4", "duration": "10 hours", "category": "Ocean", "description": "Nighttime beach waves, no loops."},
    {"title": "Hawaii Ocean White Noise (10h)", "youtube_id": "JekUNGo-RVk", "duration": "10 hours", "category": "Ocean", "description": "Pure natural white noise from Hawaii."},
    {"title": "Rolling Ocean Waves 5.1 (10h)", "youtube_id": "avrIrp7odEU", "duration": "10 hours", "category": "Ocean", "description": "Gentle surround waves for insomnia."},
    {"title": "Ocean Deep Sleep (10h)", "youtube_id": "SfqQNf-tkYM", "duration": "10 hours", "category": "Ocean", "description": "Soothing beach immersion."},
    {"title": "Ocean 10h — Ad-Free", "youtube_id": "WHPEKLQID4U", "duration": "10 hours", "category": "Ocean", "description": "No mid-roll interruptions."},
    {"title": "Ocean Crashing Waves (10h)", "youtube_id": "cjqDNEN_4ro", "duration": "10 hours", "category": "Ocean", "description": "Wave crashing beach sounds."},
    {"title": "Crackling Campfire", "youtube_id": "L_LUpnjgPso", "duration": "10 hours", "category": "Fire", "description": "Warm crackling fire."},
    {"title": "Forest Birdsong (8h)", "youtube_id": "FxAgAyZYXJ8", "duration": "8 hours", "category": "Forest", "description": "Robins and blackbirds in ancient woodland."},
    {"title": "Washington Birds (8h)", "youtube_id": "rV_ERKtNyNA", "duration": "8 hours", "category": "Forest", "description": "Colourful birds, pure nature — no music."},
    {"title": "River + Birds (8h)", "youtube_id": "ZJnaxiAH3pU", "duration": "8 hours", "category": "Forest", "description": "Mountain stream meets birdsong."},
    {"title": "Nightingale + Stream (8h)", "youtube_id": "GjKPSBHmoMo", "duration": "8 hours", "category": "Forest", "description": "One nightingale, gentle water."},
    {"title": "Pure Forest Birds (8h)", "youtube_id": "vgqQSVFch44", "duration": "8 hours", "category": "Forest", "description": "No binaurals, no music, just birds."},
    {"title": "Rain + Piano for Sleep", "youtube_id": "hZL2O2UR6Pw", "duration": "8 hours", "category": "Music", "description": "Soft rain over tender piano."},
    {"title": "Zen Flute", "youtube_id": "ZToicYcHIOU", "duration": "1 hour", "category": "Music", "description": "Meditative flute for quiet moments."},
    {"title": "Lofi Radio", "youtube_id": "jfKfPfyJRdk", "duration": "endless", "category": "Music", "description": "Lofi girl — beats to relax/study to."},
]

SCENERY_SEED = [
    {"title": "Norway — Scenic Film (12h)", "youtube_id": "KLuTLF3x9sA", "duration": "12 hours", "category": "Aerial", "description": "Fjords, cliffs, northern lights."},
    {"title": "Splendors of Nature (12h)", "youtube_id": "3xPkwNu2o8g", "duration": "12 hours", "category": "Worldwide", "description": "Mountains to reefs, thirty countries."},
    {"title": "Fantastic Views of Nature (10h)", "youtube_id": "AKeUssuu3Is", "duration": "10 hours", "category": "Aerial", "description": "Islands, forests, underwater aerials."},
    {"title": "USA Landscapes in 4K", "youtube_id": "wY3wZ4pZz2c", "duration": "27 min", "category": "Cinematic", "description": "Cinematic American wilderness."},
    {"title": "Most Beautiful Places in 4K", "youtube_id": "a-8XiE7W7u4", "duration": "1 hour", "category": "Worldwide", "description": "Global aerial beauty."},
    {"title": "BBC Earth — Rainforest Relax (3h)", "youtube_id": "eqO6ztht7vQ", "duration": "3 hours", "category": "Wildlife", "description": "Slow 4K rainforest + soft instrumental."},
    {"title": "BBC Earth — Epic Nature 4K (3h)", "youtube_id": "7ZhdXgRfxHI", "duration": "3 hours", "category": "Wildlife", "description": "Dizzying aerials — mountain to ocean."},
    {"title": "BBC Earth — Relaxing Scenes (10h)", "youtube_id": "K9g4tgKCB9g", "duration": "10 hours", "category": "Wildlife", "description": "Magical worlds of the green planet."},
    {"title": "Mountains 4K — Incredible Places", "youtube_id": "hzCc6pp9cq8", "duration": "11 hours", "category": "Cinematic", "description": "Rendered at 8K, downscaled to 4K."},
    {"title": "The Alps 4K Scenic Film", "youtube_id": "BTMjD7_evjE", "duration": "5 hours", "category": "Aerial", "description": "Possibly the most magical region in the world."},
    {"title": "Mountain Lake 4K (8h)", "youtube_id": "mD-__BYWjkw", "duration": "8 hours", "category": "Cinematic", "description": "Extended meditation with mountain lake."},
    {"title": "Colorado 4K Rockies (1h)", "youtube_id": "g4_p2-TG840", "duration": "1 hour", "category": "Cinematic", "description": "Hour-long Rocky Mountain drone."},
    {"title": "Earth's Greatest Natural Places (6h)", "youtube_id": "F70I07zTs6k", "duration": "6 hours", "category": "Worldwide", "description": "Aerial journey, no mid-roll ads."},
]

# Unsplash public photo IDs — royalty-free, hot-linkable
STILLS_SEED = [
    {"id": "photo-1470071459604-3b5ec3a7fe05", "title": "Mountain lake at dawn"},
    {"id": "photo-1472214103451-9374bd1c798e", "title": "Golden forest light"},
    {"id": "photo-1501785888041-af3ef285b470", "title": "Wooden path into the woods"},
    {"id": "photo-1441974231531-c6227db76b6e", "title": "Aspen grove in autumn"},
    {"id": "photo-1426604966848-d7adac402bff", "title": "Green valley river"},
    {"id": "photo-1506905925346-21bda4d32df4", "title": "Peaks through cloud"},
    {"id": "photo-1447752875215-b2761acb3c5d", "title": "Moss-covered ground"},
    {"id": "photo-1500534314209-a25ddb2bd429", "title": "Desert dunes at sunset"},
    {"id": "photo-1464822759023-fed622ff2c3b", "title": "Alpine mirror lake"},
    {"id": "photo-1506905925346-14b1e5dfe70a", "title": "Misty forest valley"},
    {"id": "photo-1516214104703-d870798883c5", "title": "Rocky shoreline at golden hour"},
    {"id": "photo-1511497584788-876760111969", "title": "Wildflowers by the water"},
    {"id": "photo-1519681393784-d120267933ba", "title": "Moonlit mountain"},
    {"id": "photo-1473773508845-188df298d2d1", "title": "Pine forest from above"},
    {"id": "photo-1470770841072-f978cf4d019e", "title": "Waterfall through ferns"},
    {"id": "photo-1518837695005-2083093ee35b", "title": "Ocean cliff sunset"},
    {"id": "photo-1490750967868-88aa4486c946", "title": "Cherry blossoms at rest"},
    {"id": "photo-1465146344425-f00d5f5c8f07", "title": "Path in autumn light"},
    {"id": "photo-1506197603052-3cc9c3a201bd", "title": "Pebble shoreline"},
    {"id": "photo-1518495973542-4542c06a5843", "title": "Forest sunbeams"},
    {"id": "photo-1476231682828-37e571bc172f", "title": "Mountain range at dusk"},
    {"id": "photo-1507525428034-b723cf961d3e", "title": "Turquoise bay from above"},
    {"id": "photo-1425913397330-cf8af2ff40a1", "title": "Lone tree on a hill"},
    {"id": "photo-1506318137071-a8e063b4bec0", "title": "Morning lake mirror"},
]


async def seed_if_empty():
    """Called from server startup."""
    now = datetime.now(timezone.utc).isoformat()
    for coll, seeds in [("sanctuary_sounds", SOUNDS_SEED), ("sanctuary_scenery", SCENERY_SEED)]:
        if await db[coll].count_documents({}) == 0:
            docs = [{**s, "id": str(uuid.uuid4()), "is_custom": False, "created_at": now} for s in seeds]
            if docs:
                await db[coll].insert_many(docs)
    if await db.sanctuary_stills.count_documents({}) == 0:
        docs = [{**s, "is_custom": False, "created_at": now} for s in STILLS_SEED]
        await db.sanctuary_stills.insert_many(docs)


# ============ Endpoints ============

class YTCreate(BaseModel):
    title: str
    url_or_id: str
    category: str = "Rain"
    duration: str = ""
    description: str = ""


@router.get("/sanctuary/sounds")
async def list_sounds():
    return await db.sanctuary_sounds.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.post("/sanctuary/sounds")
async def add_sound(payload: YTCreate):
    yid = extract_youtube_id(payload.url_or_id)
    if not yid:
        raise HTTPException(400, "Paste a valid YouTube URL or 11-char video ID")
    doc = {
        "id": str(uuid.uuid4()),
        "title": payload.title.strip() or "Untitled",
        "youtube_id": yid,
        "category": payload.category.strip() or "Rain",
        "duration": payload.duration.strip(),
        "description": payload.description.strip(),
        "is_custom": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.sanctuary_sounds.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.delete("/sanctuary/sounds/{sid}")
async def del_sound(sid: str):
    res = await db.sanctuary_sounds.delete_one({"id": sid, "is_custom": True})
    if res.deleted_count == 0:
        raise HTTPException(404, "Not found or seeded")
    return {"ok": True}


@router.get("/sanctuary/scenery")
async def list_scenery():
    return await db.sanctuary_scenery.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.post("/sanctuary/scenery")
async def add_scenery(payload: YTCreate):
    yid = extract_youtube_id(payload.url_or_id)
    if not yid:
        raise HTTPException(400, "Paste a valid YouTube URL or 11-char video ID")
    doc = {
        "id": str(uuid.uuid4()),
        "title": payload.title.strip() or "Untitled",
        "youtube_id": yid,
        "category": payload.category.strip() or "Aerial",
        "duration": payload.duration.strip(),
        "description": payload.description.strip(),
        "is_custom": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.sanctuary_scenery.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.delete("/sanctuary/scenery/{sid}")
async def del_scenery(sid: str):
    res = await db.sanctuary_scenery.delete_one({"id": sid, "is_custom": True})
    if res.deleted_count == 0:
        raise HTTPException(404, "Not found or seeded")
    return {"ok": True}


@router.get("/sanctuary/stills")
async def list_stills():
    return await db.sanctuary_stills.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
