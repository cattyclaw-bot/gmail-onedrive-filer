from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from .config import AppConfig
from .filer import build_message_paths, sanitize_component
from .gmail_client import AttachedEmail, GmailClient
from .state import AppState

DEFAULT_TRIAGE_QUERY = (
    "newer_than:2d -label:stluke-filed -label:stluke-tofile "
    "((subject:(invoice OR invoices OR invoicing OR expense OR expenses OR bill OR transfer OR order OR orders OR subscription OR \"tax invoice\" OR \"invoice available\" OR \"payment receipt\" OR remittance OR payout) "
    "-subject:(\"single-use code\" OR verify OR security OR \"shared the folder\" OR newsletter)) "
    "OR from:(stripe.com) "
    "OR from:(gocardless) "
    "OR (from:(lynette.polderman@hotmail.co.uk OR chriswarrell54@gmail.com) has:attachment))"
)


@dataclass(frozen=True)
class RunSummary:
    mode: str
    query: str
    fetched: int
    filed: int
    skipped: int
    planned_paths: list[str]
    dual_label_fixes: int = 0


def _write_outputs(
    paths,
    eml_data: bytes,
    body_text: str,
    attachments: list[tuple[str, bytes]],
    attached_emails: list[AttachedEmail],
    metadata: dict,
    dry_run: bool,
) -> None:
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

    used_names: set[str] = set()
    for attached in attached_emails:
        base_name = sanitize_component(attached.name, fallback="attached-email")
        folder_name = base_name
        suffix = 2
        while folder_name in used_names:
            folder_name = f"{base_name}-{suffix}"
            suffix += 1
        used_names.add(folder_name)

        attached_dir = paths.attachments_dir / folder_name
        attached_attachments_dir = attached_dir / "attachments"
        attached_dir.mkdir(parents=True, exist_ok=True)
        attached_attachments_dir.mkdir(parents=True, exist_ok=True)
        (attached_dir / "original.eml").write_bytes(attached.raw_eml)
        (attached_dir / "body.txt").write_text(attached.body_text, encoding="utf-8")
        (attached_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "subject": attached.subject,
                    "source": "top-level-attached-email",
                    "parent_message_id": metadata.get("id"),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        for name, data in attached.attachments:
            safe_name = sanitize_component(name, fallback="attachment")
            (attached_attachments_dir / safe_name).write_bytes(data)


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
        body, attachments, attached_emails = client.fetch_text_and_attachments(msg.id)
        metadata = {
            "id": msg.id,
            "subject": msg.subject,
            "internal_received_at": msg.internal_received_at.isoformat(),
            "query": effective_query,
            "mode": "sync",
        }
        _write_outputs(
            paths,
            eml,
            body,
            attachments,
            attached_emails,
            metadata,
            dry_run=dry_run,
        )
        client.mark_as_filed(msg.id, msg.internal_received_at.year)
        state.processed_ids.add(msg.id)
        filed += 1

    if not dry_run:
        state.last_sync_epoch_ms = int(datetime.now().timestamp() * 1000)
        state.save(config.state_file)

    # Cleanup: fix emails with both stluke-filed and stluke-tofile labels
    dual_label_fixes = 0
    if not dry_run:
        fixed = client.find_and_fix_dual_labels()
        dual_label_fixes = len(fixed)

    return RunSummary(
        mode="sync",
        query=effective_query,
        fetched=len(messages),
        filed=filed,
        skipped=skipped,
        planned_paths=planned_paths,
        dual_label_fixes=dual_label_fixes,
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


def run_triage(config: AppConfig, query: str | None, max_results: int | None, dry_run: bool) -> RunSummary:
    client = GmailClient(
        str(config.credentials_file),
        str(config.token_file),
        timezone=config.timezone,
    )
    effective_query = query or DEFAULT_TRIAGE_QUERY
    messages = client.list_messages(effective_query, max_results=max_results)

    tagged = 0
    planned_paths: list[str] = []
    for msg in messages:
        paths = build_message_paths(config.onedrive_root, msg.internal_received_at, msg.subject, msg.id)
        planned_paths.append(str(paths.base_dir))
        if dry_run:
            tagged += 1
            continue
        client.mark_for_filing(msg.id)
        tagged += 1

    return RunSummary(
        mode="triage",
        query=effective_query,
        fetched=len(messages),
        filed=tagged,
        skipped=0,
        planned_paths=planned_paths,
    )
