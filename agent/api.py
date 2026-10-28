"""HTTP access to the UnderCover backend."""

import os

import httpx
from dotenv import load_dotenv

load_dotenv(override=False)


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(
        base_url=os.getenv("BACKEND_URL", "http://localhost:8000"), timeout=20
    )
