from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import AppConfig
from .gmail_client import GmailClient
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

    token_test = sub.add_parser("token-test", help="Test if Gmail token is valid")

    refresh = sub.add_parser("refresh", help="Refresh Gmail OAuth token")
    refresh.add_argument("--url", help="Full redirect URL from OAuth flow")

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
    elif args.command == "token-test":
        client = GmailClient(
            str(config.credentials_file),
            str(config.token_file),
            timezone=config.timezone,
        )
        # Just try to list labels - this will fail fast if token is bad
        client._service.users().labels().list(userId="me").execute()
        print(json.dumps({"status": "ok", "message": "Token is valid"}))
        return 0
    elif args.command == "refresh":
        import os
        from google_auth_oauthlib.flow import InstalledAppFlow

        # Delete existing token to force fresh flow
        token_path = Path(config.token_file)
        if token_path.exists():
            token_path.unlink()
            print("Old token removed.")

        flow = InstalledAppFlow.from_client_secrets_file(
            str(config.credentials_file), 
            ["https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/gmail.readonly"]
        )
        flow.redirect_uri = "http://localhost"

        if args.url:
            # Extract just the code from the URL (ignore state mismatch)
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(args.url)
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            
            if not code:
                print(json.dumps({"error": "No code found in URL"}))
                return 1
                
            # Fetch token using the code directly (skip state validation)
            os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
            flow.fetch_token(code=code)
            creds = flow.credentials
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")
            print(json.dumps({"status": "ok", "message": "Token refreshed successfully"}))
            return 0
        else:
            # Generate auth URL WITHOUT PKCE (simpler for manual flow)
            auth_url, _ = flow.authorization_url(
                access_type="offline",
                include_granted_scopes="true",
                prompt="consent",
                code_challenge=None,  # Disable PKCE
            )
            print(json.dumps({"auth_url": auth_url}))
            return 0
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
