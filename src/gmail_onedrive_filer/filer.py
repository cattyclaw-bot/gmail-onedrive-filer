from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha1
from pathlib import Path

INVALID_CHARS = re.compile(r"[<>:\"/\\|?*\x00-\x1f]")


def sanitize_component(value: str, fallback: str = "untitled") -> str:
    cleaned = INVALID_CHARS.sub("_", value).strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:120] if cleaned else fallback


@dataclass(frozen=True)
class MessagePaths:
    base_dir: Path
    eml_file: Path
    body_file: Path
    attachments_dir: Path
    metadata_file: Path


def build_message_paths(root: Path, received_at: datetime, subject: str, message_id: str) -> MessagePaths:
    date_dir = root / received_at.strftime("%Y") / received_at.strftime("%m") / received_at.strftime("%d")
    sid = sha1(message_id.encode("utf-8")).hexdigest()[:12]
    msg_dir = date_dir / f"{sanitize_component(subject)}__{sid}"
    return MessagePaths(
        base_dir=msg_dir,
        eml_file=msg_dir / "original.eml",
        body_file=msg_dir / "body.txt",
        attachments_dir=msg_dir / "attachments",
        metadata_file=msg_dir / "metadata.json",
    )
