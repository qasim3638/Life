"""
Seed 4 curated sample rooms for the Tile Visualizer V1.

Run with:  python -m backend.scripts.seed_visualizer_rooms
       or:  cd /app/backend && python scripts/seed_visualizer_rooms.py

Each room is hand-tagged with a `surface_polygon` (4 corner pixel coords
of the visible floor or wall area). Customers will see these rooms on
/visualizer and be able to swap in their chosen tile.

Source images are stable Unsplash CDN URLs we picked for clear
floor/wall geometry. The polygons were measured manually in image
editor at 1024x683 (Unsplash default landscape size).
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

ROOMS = [
    {
        "id": "vis_room_kitchen_floor",
        "label": "Modern Kitchen Floor",
        "room_type": "kitchen",
        "surface_kind": "floor",
        # Bright modern open-plan kitchen with clear floor area
        "image_url": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=1024&q=80",
        # Polygon roughly outlines the visible floor — wide near camera, narrowing to back
        "surface_polygon": [[60, 660], [970, 660], [780, 360], [240, 360]],
        "default_surface_m2": 18.0,
        "tile_repeat_size_px": 220,
        "display_order": 10,
        "active": True,
    },
    {
        "id": "vis_room_bathroom_floor",
        "label": "Contemporary Bathroom Floor",
        "room_type": "bathroom",
        "surface_kind": "floor",
        "image_url": "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=1024&q=80",
        # Image is 1024x1535 portrait (NOT 1024x683 — earlier seed was wrong).
        # Trapezoid covers the visible checkered floor from the camera at the
        # bottom up to where the floor meets the toilet/sink fixtures.
        "surface_polygon": [[51, 966], [948, 966], [843, 568], [156, 568]],
        "default_surface_m2": 6.0,
        "tile_repeat_size_px": 160,
        "display_order": 20,
        "active": True,
    },
    {
        "id": "vis_room_bathroom_wall",
        "label": "Bathroom Feature Wall",
        "room_type": "bathroom",
        "surface_kind": "wall",
        "image_url": "https://images.unsplash.com/photo-1552321554-5fefe8c9ef14?w=1024&q=80",
        # Same image, 1024x1535 portrait. Polygon covers the visible
        # back wall between the ceiling line (y≈130) and the wainscoting
        # at the bottom (y≈1000). Slight perspective taper — top corners
        # are slightly inside vs bottom corners.
        "surface_polygon": [[240, 130], [790, 130], [820, 1000], [210, 1000]],
        "default_surface_m2": 8.0,
        "tile_repeat_size_px": 200,
        "display_order": 30,
        "active": True,
    },
    {
        "id": "vis_room_hallway_floor",
        "label": "Period Hallway Floor",
        "room_type": "hallway",
        "surface_kind": "floor",
        "image_url": "https://images.unsplash.com/photo-1600585154526-990dced4db0d?w=1024&q=80",
        # Image is 1024x1536 portrait — earlier polygon assumed 1024x683.
        # Trapezoid covers visible floor from camera-near (y≈1450) to
        # the receding back of the hallway at y≈760. Validator-confirmed.
        "surface_polygon": [[50, 1450], [974, 1450], [780, 760], [244, 760]],
        "default_surface_m2": 9.5,
        "tile_repeat_size_px": 180,
        "display_order": 40,
        "active": True,
    },
    # ── Round 2 — added May 2 2026 to broaden launch coverage ──
    {
        "id": "vis_room_kitchen_splashback",
        "label": "Kitchen Splashback",
        "room_type": "kitchen",
        "surface_kind": "wall",
        "image_url": "https://images.unsplash.com/photo-1565538810643-b5bdb714032a?w=1024&q=80",
        "surface_polygon": [[260, 230], [820, 230], [820, 430], [260, 430]],
        "default_surface_m2": 4.5,
        "tile_repeat_size_px": 130,
        "display_order": 50,
        "active": True,
    },
    {
        "id": "vis_room_ensuite_floor",
        "label": "Ensuite Floor",
        "room_type": "bathroom",
        "surface_kind": "floor",
        "image_url": "https://images.unsplash.com/photo-1620626011761-996317b8d101?w=1024&q=80",
        "surface_polygon": [[110, 660], [910, 660], [690, 380], [340, 380]],
        "default_surface_m2": 4.5,
        "tile_repeat_size_px": 150,
        "display_order": 60,
        "active": True,
    },
    {
        "id": "vis_room_living_floor",
        "label": "Living Room Floor",
        "room_type": "living_room",
        "surface_kind": "floor",
        "image_url": "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=1024&q=80",
        "surface_polygon": [[80, 660], [950, 660], [800, 360], [220, 360]],
        "default_surface_m2": 22.0,
        "tile_repeat_size_px": 230,
        "display_order": 70,
        "active": True,
    },
    {
        "id": "vis_room_utility_floor",
        "label": "Utility Room Floor",
        "room_type": "utility",
        "surface_kind": "floor",
        # Original Unsplash URL went 404 (May 3 2026). Hidden until the
        # admin replaces the photo via the Sample Room Editor (Edit →
        # Upload from your computer / paste new URL → Save → toggle Active).
        "image_url": "https://images.unsplash.com/photo-1556909114-44e3e9399a2e?w=1024&q=80",
        "surface_polygon": [[140, 640], [880, 640], [720, 380], [320, 380]],
        "default_surface_m2": 5.5,
        "tile_repeat_size_px": 160,
        "display_order": 80,
        "active": False,
    },
    {
        "id": "vis_room_conservatory_floor",
        "label": "Conservatory Floor",
        "room_type": "conservatory",
        "surface_kind": "floor",
        "image_url": "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=1024&q=80",
        "surface_polygon": [[100, 660], [930, 660], [780, 360], [240, 360]],
        "default_surface_m2": 16.0,
        "tile_repeat_size_px": 200,
        "display_order": 90,
        "active": True,
    },
    {
        "id": "vis_room_fireplace_wall",
        "label": "Fireplace Feature Wall",
        "room_type": "living_room",
        "surface_kind": "wall",
        "image_url": "https://images.unsplash.com/photo-1567016526105-22da7c13161a?w=1024&q=80",
        "surface_polygon": [[300, 80], [720, 80], [720, 480], [300, 480]],
        "default_surface_m2": 6.0,
        "tile_repeat_size_px": 200,
        "display_order": 100,
        "active": True,
    },
]


async def main():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        # Try loading from .env
        try:
            from dotenv import load_dotenv
            load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
            mongo_url = os.environ.get("MONGO_URL")
            db_name = os.environ.get("DB_NAME")
        except Exception:
            pass
    assert mongo_url and db_name, "MONGO_URL / DB_NAME not set"

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    upserted = 0
    for room in ROOMS:
        room["created_at"] = room.get("created_at") or datetime.now(timezone.utc).isoformat()
        room["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.visualizer_sample_rooms.update_one(
            {"id": room["id"]},
            {"$set": room},
            upsert=True,
        )
        upserted += 1
    print(f"✅ Seeded {upserted} visualizer sample rooms")


if __name__ == "__main__":
    asyncio.run(main())
