"""Environment configuration loader.

Reads from `.env` in the current working directory (or anywhere up the tree
that python-dotenv finds), with environment variables taking precedence.

All path-style settings expand `~` and environment variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _path(name: str, default: str) -> str:
    raw = os.getenv(name, default)
    return os.path.expanduser(os.path.expandvars(raw))


def _data_dir() -> Path:
    return Path(_path("TESLA_SKILL_DATA_DIR", "~/.tesla-skill"))


@dataclass(frozen=True)
class Settings:
    use_mock: bool = _bool("USE_MOCK", True)

    # Tesla developer portal credentials
    tesla_client_id: str = os.getenv("TESLA_CLIENT_ID", "")
    tesla_client_secret: str = os.getenv("TESLA_CLIENT_SECRET", "")
    tesla_redirect_uri: str = os.getenv("TESLA_REDIRECT_URI", "")

    # Region-specific endpoints (defaults for China; override for global)
    tesla_fleet_api_base: str = os.getenv(
        "TESLA_FLEET_API_BASE",
        "https://fleet-api.prd.cn.vn.cloud.tesla.cn",
    )
    tesla_auth_base: str = os.getenv("TESLA_AUTH_BASE", "https://auth.tesla.cn")

    # Token-at-rest encryption (Fernet)
    token_encryption_key: str = os.getenv("TOKEN_ENCRYPTION_KEY", "")

    # Data dir + binaries
    data_dir: Path = _data_dir()
    tesla_private_key_path: str = _path(
        "TESLA_PRIVATE_KEY_PATH", "~/.tesla-skill/tesla_keys/private.pem"
    )
    tesla_control_binary: str = _path(
        "TESLA_CONTROL_BINARY", "~/.tesla-skill/bin/tesla-control"
    )


settings = Settings()
