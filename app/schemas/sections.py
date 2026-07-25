from typing import Any
from pydantic import BaseModel, Field


class AvailabilityUpdate(BaseModel):
    available: bool


class InventoryUpdate(BaseModel):
    blood_type: str = Field(min_length=2, max_length=4)
    units: int = Field(ge=0, le=100000)


class ActionPayload(BaseModel):
    value: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VitalsPayload(BaseModel):
    temperature: float = Field(ge=20, le=50)
    heart_rate: int = Field(ge=20, le=240)
    symptoms: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=2000)
