from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import AppConfig
from .runner import run_backfill, run_plan, run_sync, run_triage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gmail-onedrive-filer")
    parser.add_argument("--root", required=True, help="Path to local OneDrive-synced root")
    parser.add_argument("--config", help="Optional JSON config file path")
    parser.add_argument("--dry-run", action="store_true", help="Plan only; do not write files")
    parser.add_argument("--verbose", action="store_true", help="Verbose logs")

    sub = parser.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync", help="Incremental/manual sync")
    sync.add_argument("--query", help="Gmail query override")
    sync.add_argument("--max", type=int, dest="max_results", help="Max messages to process")

    plan = sub.add_parser("plan", help="List planned output paths without writing files")
    plan.add_argument("--query", help="Gmail query override")
    plan.add_argument("--max", type=int, dest="max_results", help="Max messages to inspect")

    triage = sub.add_parser("triage", help="Tag likely invoice emails from last 2 days with stluke-tofile")
    triage.add_argument("--query", help="Gmail query override")
    triage.add_argument("--max", type=int, dest="max_results", help="Max messages to inspect")

    backfill = sub.add_parser("backfill", help="Historical backfill")
    backfill.add_argument("--query", help="Gmail query override")
    backfill.add_argument("--since", help="Date lower bound (YYYY/MM/DD or Gmail-supported)")
    backfill.add_argument("--until", help="Date upper bound (YYYY/MM/DD or Gmail-supported)")
    backfill.add_argument("--max", type=int, dest="max_results", help="Max messages to process")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = AppConfig.from_paths(
        onedrive_root=Path(args.root),
        config_file=Path(args.config) if args.config else None,
    )

    if args.command == "sync":
        summary = run_sync(
            config=config,
            query=args.query,
            max_results=args.max_results,
            dry_run=args.dry_run,
        )
    elif args.command == "plan":
        summary = run_plan(
            config=config,
            query=args.query,
            max_results=args.max_results,
        )
    elif args.command == "triage":
        summary = run_triage(
            config=config,
            query=args.query,
            max_results=args.max_results,
            dry_run=args.dry_run,
        )
    else:
        summary = run_backfill(
            config=config,
            query=args.query,
            since=args.since,
            until=args.until,
            max_results=args.max_results,
            dry_run=args.dry_run,
        )

    print(json.dumps(summary.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
