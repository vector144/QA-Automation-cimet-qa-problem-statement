from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
import mimetypes

mimetypes.add_type("audio/mpeg", ".mpeg")
mimetypes.add_type("audio/mpeg", ".mp3")

from database.connection import init_db
from routers import leads, ingest, scoring, reviews, export
from routers import audio


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB on startup."""
    import sys
    import os
    is_test = "pytest" in sys.modules or os.getenv("ENVIRONMENT") == "test"
    await init_db(test_mode=is_test)
    yield


app = FastAPI(
    title="CIMET QA Automation API",
    description="Automated QA scoring for sales calls",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve audio files as static assets at /audio/*
_AUDIO_DIR = Path(__file__).resolve().parent / "audio"
_AUDIO_DIR.mkdir(exist_ok=True)
app.mount("/audio", StaticFiles(directory=str(_AUDIO_DIR)), name="audio")


@app.get("/health", tags=["System"])
async def health_check():
    """Basic health check — confirms the API is running."""
    return {"status": "ok", "service": "cimet-qa-api", "version": "0.1.0"}


# Routers
app.include_router(leads.router,   prefix="/api/leads",   tags=["Leads"])
app.include_router(ingest.router,  prefix="/api/ingest",  tags=["Ingest"])
app.include_router(scoring.router, prefix="/api/scoring", tags=["Scoring"])
app.include_router(reviews.router, prefix="/api/reviews", tags=["Reviews"])
app.include_router(export.router,  prefix="/api/export",  tags=["Export"])
app.include_router(audio.router,   prefix="/api/audio",   tags=["Audio"])
