from typing import Literal
from pydantic import BaseModel, Field


BloodType = Literal["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]


class GeoPoint(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float] = Field(description="[longitude, latitude]")


class CreateBloodRequest(BaseModel):
    requester_name: str = Field(min_length=2, max_length=120)
    requester_phone: str = Field(min_length=5, max_length=40)
    hospital: str = Field(min_length=2, max_length=160)
    area: str = Field(min_length=2, max_length=120)
    location: GeoPoint | None = None
    blood_type: BloodType
    units: int = Field(default=1, ge=1, le=100)
    urgency: Literal["critical", "high", "medium"] = "critical"
    details: str = Field(default="", max_length=1000)


class AgentMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
