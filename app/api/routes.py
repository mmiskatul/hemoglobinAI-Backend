from datetime import datetime, timedelta, timezone
import secrets
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.security import create_access_token, create_refresh_token, decode_access_token, hash_password, hash_refresh_token, verify_password
from app.db.mongo import get_database
from app.core.config import get_settings
from app.schemas.auth import ForgotPasswordRequest, LoginRequest, RefreshTokenRequest, RegisterRequest, ResetPasswordRequest, TokenResponse, VerificationRequiredResponse, VerifyEmailRequest
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


@router.post("/auth/register", response_model=VerificationRequiredResponse, status_code=201)
async def register(payload: RegisterRequest):
    database = get_database()
    email = payload.email.lower()
    if await database.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Email already registered")
    code = f"{secrets.randbelow(1000000):06d}"
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.verification_code_expire_minutes)
    result = await database.users.insert_one({
        "name": payload.name.strip(), "email": email, "password_hash": hash_password(payload.password),
        "role": payload.role, "email_verified": False, "verification_code_hash": hash_refresh_token(code),
        "verification_expires_at": expires_at, "created_at": now(),
    })
    try:
        await send_email(email, "Verify your Hemoglobin AI account", f"Your verification code is: {code}\nIt expires in {settings.verification_code_expire_minutes} minutes.")
    except Exception:
        await database.users.delete_one({"_id": result.inserted_id})
        raise HTTPException(status_code=503, detail="Verification email could not be sent")
    return VerificationRequiredResponse(email=email, message="Verification code sent. Check your email.")


async def issue_tokens(user_id: str, database):
    settings = get_settings()
    refresh_token = create_refresh_token()
    await database.sessions.insert_one({
        "user_id": user_id, "token_hash": hash_refresh_token(refresh_token),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        "revoked": False, "created_at": now(),
    })
    return TokenResponse(access_token=create_access_token(user_id), refresh_token=refresh_token)


@router.post("/auth/verify-email", response_model=TokenResponse)
async def verify_email(payload: VerifyEmailRequest):
    database = get_database()
    user = await database.users.find_one({"email": payload.email.lower()})
    if not user or user.get("email_verified"):
        raise HTTPException(status_code=400, detail="Invalid or already verified account")
    if user.get("verification_expires_at", datetime.min.replace(tzinfo=timezone.utc)) < datetime.now(timezone.utc) or hash_refresh_token(payload.code) != user.get("verification_code_hash"):
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
    await database.users.update_one({"_id": user["_id"]}, {"$set": {"email_verified": True}, "$unset": {"verification_code_hash": "", "verification_expires_at": ""}})
    return await issue_tokens(str(user["_id"]), database)


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    database = get_database()
    user = await database.users.find_one({"email": payload.email.lower()})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("email_verified", False):
        raise HTTPException(status_code=403, detail="Email verification required")
    return await issue_tokens(str(user["_id"]), database)


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshTokenRequest):
    database = get_database()
    session = await database.sessions.find_one({"token_hash": hash_refresh_token(payload.refresh_token), "revoked": False, "expires_at": {"$gt": datetime.now(timezone.utc)}})
    if not session:
        raise HTTPException(status_code=401, detail="Refresh session expired or invalid")
    await database.sessions.update_one({"_id": session["_id"]}, {"$set": {"revoked": True, "revoked_at": now()}})
    return await issue_tokens(str(session["user_id"]), database)


@router.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    database = get_database()
    user = await database.users.find_one({"email": payload.email.lower()})
    message = "If that email exists, a password reset code has been sent."
    if not user:
        return {"message": message}
    code = f"{secrets.randbelow(1000000):06d}"
    settings = get_settings()
    await database.users.update_one({"_id": user["_id"]}, {"$set": {"reset_code_hash": hash_refresh_token(code), "reset_expires_at": datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_code_expire_minutes)}})
    await send_email(user["email"], "Reset your Hemoglobin AI password", f"Your password reset code is: {code}\nIt expires in {settings.password_reset_code_expire_minutes} minutes.")
    return {"message": message}


@router.post("/auth/reset-password")
async def reset_password(payload: ResetPasswordRequest):
    database = get_database()
    user = await database.users.find_one({"email": payload.email.lower()})
    if not user or user.get("reset_code_hash") != hash_refresh_token(payload.code) or user.get("reset_expires_at", datetime.min.replace(tzinfo=timezone.utc)) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")
    await database.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(payload.password)}, "$unset": {"reset_code_hash": "", "reset_expires_at": ""}})
    await database.sessions.update_many({"user_id": str(user["_id"]), "revoked": False}, {"$set": {"revoked": True, "revoked_at": now()}})
    return {"message": "Password reset successfully. Please sign in."}


@router.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    return {"id": str(user["_id"]), "name": user.get("name"), "email": user.get("email"), "role": user.get("role")}

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
