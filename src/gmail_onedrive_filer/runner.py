from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from .config import AppConfig
from .filer import build_message_paths, sanitize_component
from .gmail_client import GmailClient
from .state import AppState


@dataclass(frozen=True)
class RunSummary:
    mode: str
    query: str
    fetched: int
    filed: int
    skipped: int
    planned_paths: list[str]


def _write_outputs(paths, eml_data: bytes, body_text: str, attachments: list[tuple[str, bytes]], metadata: dict, dry_run: bool) -> None:
    if dry_run:
        return
    paths.base_dir.mkdir(parents=True, exist_ok=True)
    paths.attachments_dir.mkdir(parents=True, exist_ok=True)
    paths.eml_file.write_bytes(eml_data)
    paths.body_file.write_text(body_text, encoding="utf-8")
    paths.metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    for name, data in attachments:
        safe_name = sanitize_component(name, fallback="attachment")
        (paths.attachments_dir / safe_name).write_bytes(data)


def run_sync(config: AppConfig, query: str | None, max_results: int | None, dry_run: bool) -> RunSummary:
    state = AppState.load(config.state_file)
    client = GmailClient(
        str(config.credentials_file),
        str(config.token_file),
        timezone=config.timezone,
    )
    effective_query = query or config.default_query
    messages = client.list_messages(effective_query, max_results=max_results)

    filed = 0
    skipped = 0
    planned_paths: list[str] = []
    for msg in messages:
        if msg.id in state.processed_ids:
            skipped += 1
            continue

        paths = build_message_paths(config.onedrive_root, msg.internal_received_at, msg.subject, msg.id)
        planned_paths.append(str(paths.base_dir))
        if dry_run:
            filed += 1
            continue

        eml = client.fetch_raw_eml(msg.id)
        body, attachments = client.fetch_text_and_attachments(msg.id)
        metadata = {
            "id": msg.id,
            "subject": msg.subject,
            "internal_received_at": msg.internal_received_at.isoformat(),
            "query": effective_query,
            "mode": "sync",
        }
        _write_outputs(paths, eml, body, attachments, metadata, dry_run=dry_run)
        client.mark_as_filed(msg.id, msg.internal_received_at.year)
        state.processed_ids.add(msg.id)
        filed += 1

    if not dry_run:
        state.last_sync_epoch_ms = int(datetime.now().timestamp() * 1000)
        state.save(config.state_file)

    return RunSummary(
        mode="sync",
        query=effective_query,
        fetched=len(messages),
        filed=filed,
        skipped=skipped,
        planned_paths=planned_paths,
    )


def run_backfill(
    config: AppConfig,
    query: str | None,
    since: str | None,
    until: str | None,
    max_results: int | None,
    dry_run: bool,
) -> RunSummary:
    parts = [query or config.default_query]
    if since:
        parts.append(f"after:{since}")
    if until:
        parts.append(f"before:{until}")
    effective_query = " ".join(parts).strip()
    return run_sync(config=config, query=effective_query, max_results=max_results, dry_run=dry_run)


def run_plan(config: AppConfig, query: str | None, max_results: int | None) -> RunSummary:
    client = GmailClient(
        str(config.credentials_file),
        str(config.token_file),
        timezone=config.timezone,
    )
    effective_query = query or config.default_query
    messages = client.list_messages(effective_query, max_results=max_results)
    planned_paths = [
        str(build_message_paths(config.onedrive_root, msg.internal_received_at, msg.subject, msg.id).base_dir)
        for msg in messages
    ]
    return RunSummary(
        mode="plan",
        query=effective_query,
        fetched=len(messages),
        filed=0,
        skipped=0,
        planned_paths=planned_paths,
    )
