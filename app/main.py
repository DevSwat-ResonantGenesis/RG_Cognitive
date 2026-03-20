from fastapi import FastAPI

from .db import Base, engine
from .routers import router


app = FastAPI(title="Cognitive Service")


@app.on_event("startup")
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


app.include_router(router)


@app.get("/health")
async def root_health() -> dict:
    return {"service": "cognitive", "status": "ok"}
