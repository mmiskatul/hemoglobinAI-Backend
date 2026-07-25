from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase


async def find_matching_donors(database: AsyncIOMotorDatabase, request: dict, limit: int = 5) -> list[dict]:
    query = {
        "available": True,
        "blood_type": request["blood_type"],
        "consent_to_alerts": True,
    }
    location = request.get("location")
    if location:
        query["location"] = {
            "$near": {
                "$geometry": location,
                "$maxDistance": 100000,
            }
        }
    cursor = database.donors.find(query).limit(limit)
    donors = await cursor.to_list(length=limit)
    if not donors and location:
        donors = await database.donors.find({
            "available": True,
            "blood_type": request["blood_type"],
            "consent_to_alerts": True,
        }).limit(limit).to_list(length=limit)
    return donors


def public_donor(donor: dict) -> dict:
    return {
        "id": str(donor["_id"]),
        "name": donor["name"],
        "blood_type": donor["blood_type"],
        "area": donor["area"],
        "last_verified_at": donor.get("last_verified_at"),
    }


def now() -> datetime:
    return datetime.now(timezone.utc)
