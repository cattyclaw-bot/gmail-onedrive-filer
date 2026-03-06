from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppState:
    last_sync_epoch_ms: int | None = None
    processed_ids: set[str] = field(default_factory=set)

    @staticmethod
    def load(path: Path) -> "AppState":
        if not path.exists():
            return AppState()
        raw = json.loads(path.read_text(encoding="utf-8"))
        return AppState(
            last_sync_epoch_ms=raw.get("last_sync_epoch_ms"),
            processed_ids=set(raw.get("processed_ids", [])),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_sync_epoch_ms": self.last_sync_epoch_ms,
            "processed_ids": sorted(self.processed_ids),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
