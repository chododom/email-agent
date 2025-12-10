from contextlib import asynccontextmanager

import langsmith

from fastapi import FastAPI
from google.cloud import aiplatform
from email_agent.config import CFG
from email_agent.routes import router
from email_agent.utils.logger import logger

langsmith_client = langsmith.Client()
aiplatform.init(project=CFG.project_id, location=CFG.region)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Starting up...")

    yield
    # Shutdown actions
    logger.info("Shutting down...")


app = FastAPI(
    title="Email Agent",
    lifespan=lifespan,
)


app.include_router(router, prefix="/v1")
