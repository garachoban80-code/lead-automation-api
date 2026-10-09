import os
import secrets

from fastapi import Header, HTTPException
from app.config.loader import load_env_file


load_env_file()


def require_api_key(
    x_api_key: str = Header(default="", alias="X-API-Key"),
) -> None:
    expected = os.environ.get("API_KEY", "")

    if len(expected) < 32:
        raise HTTPException(
            status_code=503,
            detail="API authentication is not configured securely.",
        )

    if not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
