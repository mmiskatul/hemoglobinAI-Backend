import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/locations", tags=["locations"])
BASE_URL = "https://bdapis.pro.bd/geo/v2.0"


async def fetch_locations(path: str):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(BASE_URL + path)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Bangladesh location data is temporarily unavailable") from exc


@router.get("/divisions")
async def divisions():
    return await fetch_locations("/divisions")


@router.get("/districts/{division_id}")
async def districts(division_id: str):
    return await fetch_locations(f"/districts/{division_id}")


@router.get("/upazilas/{district_id}")
async def upazilas(district_id: str):
    return await fetch_locations(f"/upazilas/{district_id}")


@router.get("/unions/{upazila_id}")
async def unions(upazila_id: str):
    return await fetch_locations(f"/unions/{upazila_id}")
