"""The UnderCover backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.routes import router
from backend.store import initialize
from backend.workflow import ConflictError


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


@app.exception_handler(LookupError)
async def missing(_request: Request, exception: LookupError):
    """Return a missing-record response."""
    return JSONResponse(status_code=404, content={"detail": str(exception)})


@app.exception_handler(ConflictError)
async def conflict(_request: Request, exception: ConflictError):
    """Return a workflow conflict response."""
    return JSONResponse(status_code=409, content={"detail": str(exception)})


app.include_router(router)
