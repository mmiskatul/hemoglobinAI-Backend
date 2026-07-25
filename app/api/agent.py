from collections import Counter
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from app.api.routes import current_user
from app.db.mongo import get_database
from app.schemas.agent import AgentChatRequest, KnowledgeUpsertRequest
from app.services.agent import respond_to_dashboard
from app.services.rag import upsert_knowledge

router = APIRouter()


@router.post("/agent/chat")
async def chat_with_agent(payload: AgentChatRequest, user: dict = Depends(current_user)):
    database = get_database()
    conversation_id = ObjectId(payload.conversation_id) if payload.conversation_id and ObjectId.is_valid(payload.conversation_id) else ObjectId()
    history = await database.agent_messages.find({"conversation_id": conversation_id}).sort("created_at", 1).limit(20).to_list(length=20)
    now = datetime.now(timezone.utc)
    await database.agent_messages.insert_one({
        "conversation_id": conversation_id,
        "user_id": str(user["_id"]),
        "role": "user",
        "content": payload.message,
        "dashboard": payload.dashboard,
        "created_at": now,
    })
    answer = await respond_to_dashboard(payload.message, payload.dashboard, user, history)
    await database.agent_messages.insert_one({
        "conversation_id": conversation_id,
        "user_id": str(user["_id"]),
        "role": "assistant",
        "content": answer,
        "dashboard": payload.dashboard,
        "created_at": datetime.now(timezone.utc),
    })
    return {"conversation_id": str(conversation_id), "message": answer}


@router.post("/agent/public-chat")
async def public_chat(payload: AgentChatRequest):
    database = get_database()
    donors = await database.donors.find(
        {"available": True, "consent_to_alerts": True},
        {"_id": 0, "blood_type": 1, "area": 1},
    ).limit(1000).to_list(length=1000)
    counts = Counter((donor.get("blood_type", "unknown"), donor.get("area", "unknown")) for donor in donors)
    public_context = [
        {"blood_type": blood_type, "area": area, "available_count": count}
        for (blood_type, area), count in sorted(counts.items())
    ]
    answer = await respond_to_dashboard(
        payload.message,
        payload.dashboard,
        {"role": "public"},
        [],
        use_knowledge=False,
        public_context=public_context,
    )
    return {"message": answer, "availability": public_context}


@router.post("/agent/knowledge")
async def ingest_knowledge(payload: KnowledgeUpsertRequest, user: dict = Depends(current_user)):
    if user.get("role") not in {"agent", "hospital"}:
        raise HTTPException(status_code=403, detail="Only agent or hospital users can ingest knowledge")
    record_id = await upsert_knowledge(payload.text, payload.source)
    return {"id": record_id, "status": "indexed"}
