"""The UnderCover backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.store import initialize


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize the local business records at startup."""
    initialize()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}
