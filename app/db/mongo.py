from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import get_settings

_client: AsyncIOMotorClient | None = None


def get_database() -> AsyncIOMotorDatabase:
    global _client
    settings = get_settings()
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client[settings.mongodb_database]


async def ensure_indexes() -> None:
    database = get_database()
    await database.users.create_index("email", unique=True)
    await database.sessions.create_index("token_hash", unique=True)
    await database.sessions.create_index("expires_at", expireAfterSeconds=0)
    await database.donors.create_index([("location", "2dsphere")])
    await database.requests.create_index([("status", 1), ("blood_type", 1), ("area", 1)])
    await database.messages.create_index([("request_id", 1), ("created_at", 1)])
