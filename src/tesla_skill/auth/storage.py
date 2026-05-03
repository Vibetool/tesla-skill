"""Encrypted OAuth token storage.

Single-user personal project — keys all rows by account name (default "me").
Tokens are encrypted at rest with Fernet (AES-128-CBC + HMAC). Key comes
from TOKEN_ENCRYPTION_KEY env var.

Generate a key:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

DB lives at $TESLA_SKILL_DATA_DIR/tokens.db (defaults to ~/.tesla-skill/tokens.db).
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import asdict, dataclass

from cryptography.fernet import Fernet, InvalidToken

from tesla_skill.config import settings

log = logging.getLogger(__name__)

DEFAULT_ACCOUNT = "me"


def _db_path():
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings.data_dir / "tokens.db"


@dataclass
class TokenBundle:
    access_token: str
    refresh_token: str
    expires_at: int  # unix seconds
    id_token: str | None = None
    scope: str | None = None

    @property
    def is_near_expiry(self) -> bool:
        """True if token expires within 60s (refresh proactively)."""
        return time.time() > self.expires_at - 60


def _fernet() -> Fernet:
    key = settings.token_encryption_key
    if not key:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY not set. Generate one with:\n"
            '  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_db_path())
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS tokens (
            account TEXT PRIMARY KEY,
            data_encrypted BLOB NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    return c


def save(bundle: TokenBundle, account: str = DEFAULT_ACCOUNT) -> None:
    f = _fernet()
    payload = json.dumps(asdict(bundle)).encode()
    encrypted = f.encrypt(payload)
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO tokens (account, data_encrypted, updated_at) VALUES (?, ?, ?)",
            (account, encrypted, int(time.time())),
        )
    log.info("Saved tokens for account=%s (expires_at=%s)", account, bundle.expires_at)


def load(account: str = DEFAULT_ACCOUNT) -> TokenBundle | None:
    with _conn() as c:
        row = c.execute(
            "SELECT data_encrypted FROM tokens WHERE account = ?", (account,)
        ).fetchone()
    if not row:
        return None
    try:
        decrypted = _fernet().decrypt(row[0])
    except InvalidToken:
        raise RuntimeError(
            "Failed to decrypt stored token. Wrong TOKEN_ENCRYPTION_KEY? "
            "If you rotated the key, delete tokens.db and re-authorize."
        )
    data = json.loads(decrypted)
    return TokenBundle(**data)


def delete(account: str = DEFAULT_ACCOUNT) -> None:
    with _conn() as c:
        c.execute("DELETE FROM tokens WHERE account = ?", (account,))
    log.info("Deleted tokens for account=%s", account)
