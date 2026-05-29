from fastapi import APIRouter

from app.api.v1.chats.routes import router as chats_router

router = APIRouter(prefix="/v1")
router.include_router(chats_router)
