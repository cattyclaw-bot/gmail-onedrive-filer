"""Start a state- and PKCE-protected Gmail OAuth reauthorisation."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

PROJECT = Path(__file__).resolve().parents[1]
SECRETS = PROJECT / "secrets"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.readonly",
]

def atomic_write_private(path: Path, payload: dict[str, object]) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        os.unlink(temporary)
        raise

def main() -> None:
    flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS / "google-credentials.json"), SCOPES)
    flow.redirect_uri = "http://localhost"
    flow.code_verifier = os.urandom(48).hex()
    url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent",
    )
    atomic_write_private(SECRETS / "reauth-pending.json", {
        "state": state, "code_verifier": flow.code_verifier,
        "redirect_uri": flow.redirect_uri, "scopes": SCOPES,
    })
    print(url)

if __name__ == "__main__":
    main()
