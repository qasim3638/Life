"""
Database and application configuration
"""
import os
from motor.motor_asyncio import AsyncIOMotorClient

# Environment variables - MONGO_URL is required, no fallback to localhost
MONGO_URL = os.environ.get("MONGO_URL")
if not MONGO_URL:
    raise ValueError("MONGO_URL environment variable is required")
DB_NAME = os.environ.get("DB_NAME", "tile_station")
JWT_SECRET = os.environ.get("JWT_SECRET", "your-secret-key-change-in-production")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")

# Database client (initialized lazily)
_client = None
_db = None

def get_client():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URL)
    return _client

def get_db():
    global _db
    if _db is None:
        _db = get_client()[DB_NAME]
    return _db

# Shortcut
db = property(lambda self: get_db())
