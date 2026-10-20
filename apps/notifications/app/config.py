"""Settings, all from environment variables (same names as the other services where they overlap)."""
import os
from dataclasses import dataclass, field
from urllib.parse import quote


def database_url() -> str:
    """DATABASE_URL, or one built from the same POSTGRES_* variables as the core API."""
    if url := os.getenv("DATABASE_URL"):
        return url
    user = quote(os.getenv("POSTGRES_USER", "mediflow"), safe="")
    password = quote(os.getenv("POSTGRES_PASSWORD", ""), safe="")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    name = os.getenv("POSTGRES_DB", "mediflow")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def _list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass
class Settings:
    database_url: str = field(default_factory=database_url)
    jwks_url: str = field(default_factory=lambda: os.getenv("JWKS_URL", "http://localhost:8000/api/auth/jwks"))
    jwt_issuer: str = field(default_factory=lambda: os.getenv("JWT_ISSUER", "mediflow-core"))
    jwt_audience: str = field(default_factory=lambda: os.getenv("JWT_AUDIENCE", "mediflow"))
    time_zone: str = field(default_factory=lambda: os.getenv("TIME_ZONE", "Africa/Lagos"))
    # Extra delivery channels on top of in-app: "email", "sms". Empty = in-app only.
    channels: list[str] = field(default_factory=lambda: _list(os.getenv("NOTIFY_CHANNELS", "")))
    # Turn the event listener and scheduled jobs off to run the API alone (tests, or a second API replica).
    listen: bool = field(default_factory=lambda: os.getenv("LISTEN_EVENTS", "1") != "0")
