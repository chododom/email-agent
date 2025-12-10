from fastapi import APIRouter

from email_agent.routes.agent_router import router as agent_router
from email_agent.routes.watch_router import router as watch_router
from email_agent.routes.ingest_router import router as ingest_router

router = APIRouter()
router.include_router(agent_router)
router.include_router(watch_router)
router.include_router(ingest_router)
