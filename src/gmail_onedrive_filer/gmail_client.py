from __future__ import annotations

import base64
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from .filer import sanitize_component

# Request both scopes because Google often returns modify+readonly together
# and oauthlib treats scope mismatches as an error.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.readonly",
]
TOFILE_LABEL = "stluke-tofile"
FILED_LABEL = "stluke-filed"


@dataclass(frozen=True)
class GmailMessage:
    id: str
    subject: str
    internal_received_at: datetime


class GmailClient:
    def __init__(self, credentials_file: str, token_file: str, timezone: str = "UTC") -> None:
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.timezone = timezone
        self._service = self._build_service()

    @staticmethod
    def _decode_b64url(value: str | None) -> bytes:
        if not value:
            return b""
        return base64.urlsafe_b64decode(value.encode("ascii"))

    @staticmethod
    def _header_value(headers: Iterable[dict], name: str) -> str:
        target = name.lower()
        for header in headers:
            if str(header.get("name", "")).lower() == target:
                return str(header.get("value", ""))
        return ""

    @staticmethod
    def _html_to_text(html: str) -> str:
        text = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", "", html)
        text = re.sub(r"(?is)<br\\s*/?>", "\n", text)
        text = re.sub(r"(?is)</p\\s*>", "\n\n", text)
        text = re.sub(r"(?is)<[^>]+>", "", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        return text.strip()

    @staticmethod
    def _safe_attachment_name(name: str, fallback_index: int) -> str:
        if not name:
            return f"attachment-{fallback_index}"
        safe = sanitize_component(name, fallback=f"attachment-{fallback_index}")
        return safe

    def _build_service(self):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except Exception as exc:  # pragma: no cover - depends on runtime deps
            raise RuntimeError(
                "Missing Gmail dependencies. Install project deps first "
                "(google-api-python-client, google-auth, google-auth-oauthlib)."
            ) from exc

        creds = None
        token_path = Path(self.token_file)
        credentials_path = Path(self.credentials_file)

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not credentials_path.exists():
                    raise FileNotFoundError(
                        f"Gmail OAuth credentials file not found: {credentials_path}"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), SCOPES
                )
                if hasattr(flow, "run_console"):
                    # Prefer Google's console flow when available.
                    creds = flow.run_console(
                        authorization_prompt_message=(
                            "Open this URL in your browser to authorize Gmail access:\n{url}\n"
                        ),
                        authorization_code_message=(
                            "Paste the full redirect URL or just the code: "
                        ),
                    )
                else:
                    # Fallback for versions without run_console().
                    flow.redirect_uri = "http://localhost"
                    auth_url, _state = flow.authorization_url(
                        access_type="offline",
                        include_granted_scopes="true",
                        prompt="consent",
                    )
                    print(
                        "Open this URL in your browser to authorize Gmail access:\n"
                        f"{auth_url}\n"
                    )
                    entered = input("Paste the full redirect URL or just the code: ").strip()
                    if entered.startswith("http://") or entered.startswith("https://"):
                        # Use the full redirect URL when available to preserve state/code handling.
                        if entered.startswith("http://localhost"):
                            # OAuth installed-app flow commonly uses localhost callback URLs.
                            os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
                        flow.fetch_token(authorization_response=entered)
                        creds = flow.credentials
                    else:
                        code = entered
                        if not code:
                            raise RuntimeError("No OAuth code detected from input.")
                        flow.fetch_token(code=code)
                        creds = flow.credentials
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")

        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    def _get_or_create_label_id(self, label_name: str) -> str:
        labels_resp = self._service.users().labels().list(userId="me").execute()
        labels = labels_resp.get("labels", [])
        for label in labels:
            if str(label.get("name", "")).lower() == label_name.lower():
                return str(label["id"])

        create_resp = (
            self._service.users()
            .labels()
            .create(
                userId="me",
                body={
                    "name": label_name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        return str(create_resp["id"])

    def _find_label_id(self, label_name: str) -> str | None:
        labels_resp = self._service.users().labels().list(userId="me").execute()
        labels = labels_resp.get("labels", [])
        for label in labels:
            if str(label.get("name", "")).lower() == label_name.lower():
                return str(label["id"])
        return None

    def list_messages(self, query: str, max_results: int | None = None) -> list[GmailMessage]:
        messages: list[GmailMessage] = []
        page_token = None
        tz = ZoneInfo(self.timezone)
        remaining = max_results

        while True:
            kwargs = {"userId": "me", "q": query}
            if page_token:
                kwargs["pageToken"] = page_token
            if remaining is not None:
                kwargs["maxResults"] = min(remaining, 500)

            response = self._service.users().messages().list(**kwargs).execute()
            refs = response.get("messages", [])

            for ref in refs:
                message_id = ref["id"]
                msg = (
                    self._service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=message_id,
                        format="metadata",
                        metadataHeaders=["Subject"],
                    )
                    .execute()
                )
                internal_ms = int(msg.get("internalDate", "0"))
                internal_dt = datetime.fromtimestamp(internal_ms / 1000, tz=tz)
                subject = self._header_value(msg.get("payload", {}).get("headers", []), "Subject")
                messages.append(
                    GmailMessage(
                        id=message_id,
                        subject=subject or "(no subject)",
                        internal_received_at=internal_dt,
                    )
                )
                if remaining is not None:
                    remaining -= 1
                    if remaining <= 0:
                        return messages

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return messages

    def fetch_raw_eml(self, message_id: str) -> bytes:
        msg = (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id, format="raw")
            .execute()
        )
        return self._decode_b64url(msg.get("raw"))

    def fetch_text_and_attachments(self, message_id: str) -> tuple[str, list[tuple[str, bytes]]]:
        msg = (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        payload = msg.get("payload", {})

        plain_chunks: list[str] = []
        html_chunks: list[str] = []
        attachments: list[tuple[str, bytes]] = []
        seen_names: set[str] = set()

        def walk_part(part: dict, idx_counter: list[int]) -> None:
            mime_type = part.get("mimeType", "")
            filename = str(part.get("filename", "") or "")
            body = part.get("body", {}) or {}
            data = body.get("data")
            attachment_id = body.get("attachmentId")

            if mime_type.startswith("multipart/"):
                for child in part.get("parts", []) or []:
                    walk_part(child, idx_counter)
                return

            if filename and attachment_id:
                idx_counter[0] += 1
                raw_name = self._safe_attachment_name(filename, idx_counter[0])
                name = raw_name
                suffix = 2
                while name in seen_names:
                    name = f"{raw_name}-{suffix}"
                    suffix += 1
                seen_names.add(name)

                raw = (
                    self._service.users()
                    .messages()
                    .attachments()
                    .get(userId="me", messageId=message_id, id=attachment_id)
                    .execute()
                )
                attachments.append((name, self._decode_b64url(raw.get("data"))))
                return

            if not data:
                return

            text = self._decode_b64url(data).decode("utf-8", errors="replace").strip()
            if not text:
                return

            if mime_type == "text/plain":
                plain_chunks.append(text)
            elif mime_type == "text/html":
                html_chunks.append(text)

        walk_part(payload, [0])
        if plain_chunks:
            body_text = "\n\n".join(plain_chunks).strip()
        elif html_chunks:
            body_text = self._html_to_text("\n\n".join(html_chunks))
        else:
            body_text = ""

        return body_text, attachments

    def mark_as_filed(self, message_id: str, year: int) -> None:
        tofile_id = self._find_label_id(TOFILE_LABEL)
        filed_id = self._get_or_create_label_id(FILED_LABEL)
        year_id = self._get_or_create_label_id(str(year))

        body: dict[str, list[str]] = {
            "addLabelIds": [filed_id, year_id],
            "removeLabelIds": [],
        }
        if tofile_id:
            body["removeLabelIds"].append(tofile_id)

        (
            self._service.users()
            .messages()
            .modify(userId="me", id=message_id, body=body)
            .execute()
        )

    def mark_for_filing(self, message_id: str) -> None:
        tofile_id = self._get_or_create_label_id(TOFILE_LABEL)
        (
            self._service.users()
            .messages()
            .modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": [tofile_id], "removeLabelIds": []},
            )
            .execute()
        )
