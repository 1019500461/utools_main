from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.common.responses import success
from app.core.config import settings
from app.db.session import close_database, init_database
from app.modules.role.api import router as role_router
from app.modules.user.api import router as user_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_database()
    yield
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
app.include_router(role_router)


@app.get("/health")
async def health():
    return success({"status": "ok"})
