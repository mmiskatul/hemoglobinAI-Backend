from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.api.sections import router as sections_router
from app.api.agent import router as agent_router
from app.core.config import get_settings
from app.db.mongo import ensure_indexes


@asynccontextmanager
async def lifespan(_: FastAPI):
    await ensure_indexes()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router, prefix=settings.api_prefix)
app.include_router(sections_router, prefix=settings.api_prefix)
app.include_router(agent_router, prefix=settings.api_prefix)


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.app_name}
