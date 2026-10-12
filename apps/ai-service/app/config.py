import os
from dataclasses import dataclass

DEV_TOKEN = "mediflow-dev-internal-token"


@dataclass(frozen=True)
class Settings:
    env: str
    internal_token: str
    emergency_number: str


def load_settings() -> Settings:
    env = os.getenv("AI_ENV", "development")
    token = os.getenv("AI_SERVICE_TOKEN", DEV_TOKEN)
    if env != "development" and token == DEV_TOKEN:
        raise RuntimeError("AI_SERVICE_TOKEN must be set to a unique secret outside development.")
    return Settings(env=env, internal_token=token, emergency_number=os.getenv("EMERGENCY_NUMBER", "112"))
