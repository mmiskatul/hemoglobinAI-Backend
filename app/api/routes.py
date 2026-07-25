from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.db.mongo import get_database
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.requests import AgentMessageRequest, CreateBloodRequest
from app.services.agent import respond_to_request
from app.services.matching import find_matching_donors, now, public_donor
from app.services.notifications import send_email

router = APIRouter()
bearer = HTTPBearer(auto_error=False)


async def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        user_id = decode_access_token(credentials.credentials)
        user = await get_database().users.find_one({"_id": ObjectId(user_id)})
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.post("/auth/register", response_model=TokenResponse, status_code=201)
async def register(payload: RegisterRequest):
    database = get_database()
    if await database.users.find_one({"email": payload.email.lower()}):
        raise HTTPException(status_code=409, detail="Email already registered")
    result = await database.users.insert_one({
        "name": payload.name.strip(),
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
        "role": payload.role,
        "created_at": now(),
    })
    return TokenResponse(access_token=create_access_token(str(result.inserted_id)))


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    user = await get_database().users.find_one({"email": payload.email.lower()})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(str(user["_id"])))


@router.post("/requests", status_code=201)
async def create_request(payload: CreateBloodRequest, user: dict = Depends(current_user)):
    database = get_database()
    document = payload.model_dump()
    document.update({
        "requester_id": str(user["_id"]),
        "status": "matching",
        "created_at": now(),
        "updated_at": now(),
    })
    result = await database.requests.insert_one(document)
    document["_id"] = result.inserted_id
    donors = await find_matching_donors(database, document)
    donor_ids = [donor["_id"] for donor in donors]
    await database.requests.update_one({"_id": result.inserted_id}, {"$set": {"donor_ids": donor_ids, "status": "awaiting_confirmation", "updated_at": now()}})
    await database.messages.insert_one({
        "request_id": result.inserted_id,
        "role": "system",
        "content": f"The coordination agent found {len(donors)} matching donor(s), prioritizing {payload.area}.",
        "created_at": now(),
    })
    return {
        "request_id": str(result.inserted_id),
        "status": "awaiting_confirmation" if donors else "matching",
        "matches": [public_donor(donor) for donor in donors],
        "notification": "The agent has received the request and started area-based matching.",
    }


@router.get("/requests/{request_id}/messages")
async def list_messages(request_id: str, user: dict = Depends(current_user)):
    if not ObjectId.is_valid(request_id):
        raise HTTPException(status_code=404, detail="Request not found")
    messages = await get_database().messages.find({"request_id": ObjectId(request_id)}).sort("created_at", 1).to_list(length=100)
    return {"messages": [{"role": item["role"], "content": item["content"], "created_at": item["created_at"]} for item in messages]}


@router.post("/requests/{request_id}/messages")
async def message_agent(request_id: str, payload: AgentMessageRequest, user: dict = Depends(current_user)):
    if not ObjectId.is_valid(request_id):
        raise HTTPException(status_code=404, detail="Request not found")
    database = get_database()
    request = await database.requests.find_one({"_id": ObjectId(request_id)})
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    await database.messages.insert_one({"request_id": request["_id"], "role": "user", "content": payload.message, "created_at": now()})
    donors = await database.donors.find({"_id": {"$in": request.get("donor_ids", [])}}).to_list(length=5)
    answer = await respond_to_request(request, donors, payload.message)
    await database.messages.insert_one({"request_id": request["_id"], "role": "agent", "content": answer, "created_at": now()})
    return {"role": "agent", "content": answer}


@router.post("/requests/{request_id}/confirm")
async def confirm_request(request_id: str, user: dict = Depends(current_user)):
    if not ObjectId.is_valid(request_id):
        raise HTTPException(status_code=404, detail="Request not found")
    database = get_database()
    request = await database.requests.find_one({"_id": ObjectId(request_id), "requester_id": str(user["_id"])})
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    await database.requests.update_one({"_id": request["_id"]}, {"$set": {"status": "confirmed", "updated_at": now()}})
    donors = await database.donors.find({"_id": {"$in": request.get("donor_ids", [])}}).to_list(length=5)
    for donor in donors:
        donor_user = await database.users.find_one({"donor_id": donor["_id"]})
        if donor_user and donor_user.get("email"):
            await send_email(donor_user["email"], "Hemoglobin AI blood request", f"A verified request is available in your area. Please open your dashboard to accept or decline.")
    return {"status": "confirmed", "message": "Donor notifications queued. Contact details remain protected until donor consent."}
