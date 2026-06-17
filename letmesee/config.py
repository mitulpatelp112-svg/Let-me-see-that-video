"""Configuration loading.

Reads settings from environment variables, falling back to a ``.env`` file in
the current working directory (or the path given by ``LMS_ENV_FILE``). No third
party dependency is required for this — it is a tiny ``KEY=VALUE`` parser.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_int_set(value: str | None) -> set[int]:
    result: set[int] = set()
    if not value:
        return result
    for chunk in value.replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk:
            try:
                result.add(int(chunk))
            except ValueError:
                continue
    return result


@dataclass
class Config:
    """Runtime configuration for the absorber and the bot."""

    telegram_token: str | None = None
    # Empty set means "anyone may use the bot". Strongly recommended to set this.
    allowed_user_ids: set[int] = field(default_factory=set)
    library_dir: Path = Path("library")
    # Download the full video file (needs disk space). Metadata + transcript are
    # always absorbed regardless of this flag.
    download_video: bool = False
    # Download just the audio track (useful for transcription).
    download_audio: bool = False
    # Attempt local Whisper transcription when no captions are available.
    transcribe: bool = False
    whisper_model: str = "base"
    # Long-poll timeout (seconds) for the Telegram getUpdates call.
    poll_timeout: int = 50

    @classmethod
    def load(cls, env_file: str | os.PathLike[str] | None = None) -> "Config":
        env_path = Path(env_file or os.environ.get("LMS_ENV_FILE", ".env"))
        file_values = _load_env_file(env_path)

        def get(key: str) -> str | None:
            return os.environ.get(key, file_values.get(key))

        return cls(
            telegram_token=get("TELEGRAM_BOT_TOKEN") or None,
            allowed_user_ids=_as_int_set(get("TELEGRAM_ALLOWED_USERS")),
            library_dir=Path(get("LIBRARY_DIR") or "library"),
            download_video=_as_bool(get("DOWNLOAD_VIDEO"), False),
            download_audio=_as_bool(get("DOWNLOAD_AUDIO"), False),
            transcribe=_as_bool(get("TRANSCRIBE"), False),
            whisper_model=get("WHISPER_MODEL") or "base",
            poll_timeout=int(get("POLL_TIMEOUT") or 50),
        )
