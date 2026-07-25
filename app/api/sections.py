from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from app.api.routes import current_user
from app.db.mongo import get_database
from app.schemas.sections import ActionPayload, AvailabilityUpdate, InventoryUpdate, VitalsPayload

router = APIRouter()


def now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/notifications")
async def notifications(user: dict = Depends(current_user)):
    items = await get_database().notifications.find({"user_id": str(user["_id"])}).sort("created_at", -1).limit(100).to_list(length=100)
    return {"notifications": [{"id": str(item["_id"]), "type": item["type"], "message": item["message"], "read": item.get("read", False), "created_at": item["created_at"]} for item in items]}


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, user: dict = Depends(current_user)):
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    result = await get_database().notifications.update_one({"_id": ObjectId(notification_id), "user_id": str(user["_id"])}, {"$set": {"read": True}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "read"}


@router.get("/donors/me")
async def donor_profile(user: dict = Depends(current_user)):
    donor = await get_database().donors.find_one({"user_id": str(user["_id"])})
    return {"profile": donor or {"name": user.get("name"), "available": False, "area": None}}


@router.patch("/donors/me/availability")
async def donor_availability(payload: AvailabilityUpdate, user: dict = Depends(current_user)):
    result = await get_database().donors.update_one({"user_id": str(user["_id"])}, {"$set": {"available": payload.available, "updated_at": now()}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Donor profile not found")
    return {"available": payload.available}


@router.get("/donors/me/requests")
async def donor_requests(user: dict = Depends(current_user)):
    donor = await get_database().donors.find_one({"user_id": str(user["_id"])}, {"_id": 1})
    if not donor:
        return {"requests": []}
    requests = await get_database().requests.find({"donor_ids": donor["_id"]}).sort("created_at", -1).limit(50).to_list(length=50)
    return {"requests": [{"id": str(item["_id"]), "blood_type": item["blood_type"], "area": item["area"], "status": item["status"], "units": item["units"]} for item in requests]}


@router.get("/hospitals/inventory")
async def hospital_inventory(user: dict = Depends(current_user)):
    items = await get_database().inventory.find({"owner_id": str(user["_id"])}).sort("blood_type", 1).to_list(length=100)
    return {"inventory": [{"id": str(item["_id"]), "blood_type": item["blood_type"], "units": item["units"], "updated_at": item["updated_at"]} for item in items]}


@router.put("/hospitals/inventory")
async def update_inventory(payload: InventoryUpdate, user: dict = Depends(current_user)):
    await get_database().inventory.update_one(
        {"owner_id": str(user["_id"]), "blood_type": payload.blood_type},
        {"$set": {"owner_id": str(user["_id"]), "blood_type": payload.blood_type, "units": payload.units, "updated_at": now()}},
        upsert=True,
    )
    return {"status": "updated", "blood_type": payload.blood_type, "units": payload.units}


@router.post("/hospitals/orders")
async def hospital_order(payload: ActionPayload, user: dict = Depends(current_user)):
    document = {"owner_id": str(user["_id"]), "type": "blood_order", "payload": payload.model_dump(), "status": "submitted", "created_at": now()}
    result = await get_database().hospital_orders.insert_one(document)
    return {"id": str(result.inserted_id), "status": "submitted"}


@router.get("/hospitals/orders")
async def hospital_orders(user: dict = Depends(current_user)):
    items = await get_database().hospital_orders.find({"owner_id": str(user["_id"])}).sort("created_at", -1).limit(100).to_list(length=100)
    return {"orders": [{"id": str(item["_id"]), "status": item["status"], "payload": item["payload"], "created_at": item["created_at"]} for item in items]}


@router.post("/hospitals/broadcasts")
async def hospital_broadcast(payload: ActionPayload, user: dict = Depends(current_user)):
    document = {"owner_id": str(user["_id"]), "type": "donor_broadcast", "payload": payload.model_dump(), "created_at": now()}
    result = await get_database().broadcasts.insert_one(document)
    return {"id": str(result.inserted_id), "status": "queued", "message": "Area-based donor notifications queued."}


@router.get("/courier/tasks")
async def courier_tasks(user: dict = Depends(current_user)):
    items = await get_database().dispatches.find({"courier_id": str(user["_id"])}).sort("created_at", -1).limit(100).to_list(length=100)
    return {"tasks": [{"id": str(item["_id"]), "status": item["status"], "route": item.get("route"), "created_at": item["created_at"]} for item in items]}


@router.post("/courier/tasks/{task_id}/complete")
async def complete_courier_task(task_id: str, payload: ActionPayload, user: dict = Depends(current_user)):
    if not ObjectId.is_valid(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    result = await get_database().dispatches.update_one({"_id": ObjectId(task_id), "courier_id": str(user["_id"])}, {"$set": {"status": "completed", "proof": payload.model_dump(), "completed_at": now()}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "completed"}


@router.post("/requester/vitals")
async def requester_vitals(payload: VitalsPayload, user: dict = Depends(current_user)):
    result = await get_database().vitals.insert_one({"user_id": str(user["_id"]), **payload.model_dump(), "created_at": now()})
    return {"id": str(result.inserted_id), "status": "saved"}
