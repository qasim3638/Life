"""
Pytest config — shared session-scoped asyncio event loop + .env bootstrap.

Motor (AsyncIOMotorClient) is created at module import time inside
`config.get_db()`, bound to whatever loop is active then. When pytest-asyncio's
default function-scoped loops close between tests, subsequent async tests that
touch Motor get `RuntimeError: Event loop is closed`.

Making the loop session-scoped keeps Motor happy.

Also: `services/__init__.py` imports `config.py` which requires MONGO_URL
at import time. Tests that import `services.*` directly need .env loaded
before the import — done at the top of this conftest.
"""
import os
import sys
import asyncio
import pytest
from pathlib import Path
from dotenv import load_dotenv

# Bootstrap env before any test module is imported, AND make
# `/app/backend` importable so `from services.seo_autonomous import ...`
# resolves the same way the running app sees it.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))
load_dotenv(_BACKEND_ROOT / ".env")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "tile_station")


@pytest.fixture(scope="session")
def event_loop():
    """Override pytest-asyncio's default function-scoped loop with a session
    one, so Motor's client survives across test_* boundaries."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
