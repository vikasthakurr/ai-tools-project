"""
FastAPI application entry point.
Text-to-SQL: Convert natural language questions to SQL queries.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.config import settings
from app.api.routes import router
from app.services.database_service import db_service
from app.services.ai_service import ai_service
from app.utils.logger import setup_logging, logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    # Startup
    setup_logging(settings.log_level)
    logger.info(f"Starting Text-to-SQL API [{settings.environment}]")
    logger.info(f"Database: {settings.database_path}")
    logger.info(f"Model: {settings.gemini_model}")

    db_service.connect()
    ai_service.configure()

    logger.info("Application ready")
    yield

    # Shutdown
    db_service.disconnect()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Text-to-SQL API",
    description="Convert natural language questions into SQL queries and get results from an e-commerce database.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
if settings.is_production:
    origins = []  # In production, frontend is served from same origin — no CORS needed
else:
    origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False if origins == ["*"] else True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# API routes
app.include_router(router, prefix="/api")

# Serve static frontend files
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
