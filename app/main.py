from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from tortoise import connections

from app.common.responses import success
from app.core.config import settings
from app.db.session import close_database, init_database
from app.modules.etf.api import router as etf_router
from app.modules.etf.monitor import start_scheduler, stop_scheduler
from app.modules.role.api import router as role_router
from app.modules.user.admin_api import router as user_admin_router
from app.modules.user.api import router as user_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_database()
    start_scheduler()
    yield
    await stop_scheduler()
    await close_database()


app = FastAPI(title=settings.app_title, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(user_router)
app.include_router(user_admin_router)
app.include_router(role_router)
app.include_router(etf_router)


@app.get("/health")
async def health():
    return success({"status": "ok"})


@app.get("/health/db")
async def health_db():
    try:
        connection = connections.get("default")
        await connection.execute_query("SELECT 1")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return success({"status": "ok", "database": "ok"})
