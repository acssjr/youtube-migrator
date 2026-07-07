import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config.config import settings
from app.database.db import init_db
from app.api import auth, channels, migrations, settings as settings_api, logs
from app.services.queue_service import QueueService

# Configure Loguru to write to separate logs files based on context/level
settings.ensure_directories()

# Remove standard handlers
logger.remove()

# 1. Console logging
logger.add(sys.stdout, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

# 2. Downloads logs
logger.add(
    str(settings.logs_path / "downloads.log"),
    filter=lambda record: "downloader_service" in record["name"] or "download" in record["message"].lower(),
    level="INFO",
    rotation="10 MB",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:8} | {message}"
)

# 3. Uploads logs
logger.add(
    str(settings.logs_path / "uploads.log"),
    filter=lambda record: "youtube_service" in record["name"] or "upload" in record["message"].lower(),
    level="INFO",
    rotation="10 MB",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:8} | {message}"
)

# 4. Errors logs
logger.add(
    str(settings.logs_path / "errors.log"),
    filter=lambda record: record["level"].name in ["ERROR", "CRITICAL"],
    level="ERROR",
    rotation="10 MB",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:8} | {name}:{line} | {message}"
)

# FastAPI application initialization
app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for automating migrations between YouTube channels",
    version="0.1.0"
)

# CORS setup for React Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In development, allow all. Or change to ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix="/api")
app.include_router(channels.router, prefix="/api")
app.include_router(migrations.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")
app.include_router(logs.router, prefix="/api")

@app.on_event("startup")
def on_startup():
    logger.info("Initializing database...")
    init_db()
    
    logger.info("Starting background migration queue...")
    queue = QueueService.get_instance()
    queue.start()

@app.on_event("shutdown")
def on_shutdown():
    logger.info("Shutting down background queue...")
    QueueService.get_instance().stop()

@app.get("/")
def read_root():
    return {"app": settings.APP_NAME, "status": "running"}
