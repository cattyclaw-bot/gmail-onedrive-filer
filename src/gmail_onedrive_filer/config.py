from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_QUERY = "-in:spam -in:trash"


@dataclass(frozen=True)
class AppConfig:
    onedrive_root: Path
    credentials_file: Path
    token_file: Path
    state_file: Path
    timezone: str
    default_query: str

    @staticmethod
    def from_paths(
        onedrive_root: Path,
        config_file: Path | None = None,
    ) -> "AppConfig":
        config_data: dict[str, str] = {}
        if config_file and config_file.exists():
            config_data = json.loads(config_file.read_text(encoding="utf-8"))

        def pick(key: str, env_key: str, fallback: str) -> str:
            return str(config_data.get(key) or os.getenv(env_key) or fallback)

        credentials = Path(pick("credentials_file", "GMAIL_CREDENTIALS_FILE", "./secrets/google-credentials.json"))
        token = Path(pick("token_file", "GMAIL_TOKEN_FILE", "./secrets/google-token.json"))
        state = Path(pick("state_file", "FILER_STATE_FILE", "./state/state.json"))
        timezone = pick("timezone", "FILER_TIMEZONE", "Europe/London")
        default_query = pick("default_query", "GMAIL_DEFAULT_QUERY", DEFAULT_QUERY)

        return AppConfig(
            onedrive_root=onedrive_root,
            credentials_file=credentials,
            token_file=token,
            state_file=state,
            timezone=timezone,
            default_query=default_query,
        )
