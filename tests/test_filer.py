from datetime import datetime
from pathlib import Path

from gmail_onedrive_filer.filer import build_message_paths, sanitize_component
from gmail_onedrive_filer.gmail_client import AttachedEmail
from gmail_onedrive_filer.runner import _write_outputs


def test_sanitize_component_removes_invalid_chars() -> None:
    value = 'hello<>:"/\\|?*world'
    assert sanitize_component(value) == "hello_________world"


def test_build_message_paths_uses_date_tree() -> None:
    root = Path("/tmp/onedrive")
    dt = datetime(2026, 3, 6, 12, 0, 0)
    paths = build_message_paths(root, dt, "Subject", "msg-1")
    assert "/2026/03/06/" in str(paths.base_dir)
    assert paths.eml_file.name == "original.eml"


def test_write_outputs_expands_top_level_attached_emails(tmp_path: Path) -> None:
    paths = build_message_paths(
        tmp_path,
        datetime(2026, 3, 6, 12, 0, 0),
        "Parent",
        "msg-parent",
    )
    attached = AttachedEmail(
        name="Attached Email.eml",
        subject="Attached Subject",
        raw_eml=b"From: a@example.com\nSubject: Attached Subject\n\nHello",
        body_text="Hello",
        attachments=[("invoice.pdf", b"pdf-bytes")],
    )
    _write_outputs(
        paths=paths,
        eml_data=b"raw-parent",
        body_text="Parent body",
        attachments=[("top.txt", b"top-data")],
        attached_emails=[attached],
        metadata={"id": "msg-parent"},
        dry_run=False,
    )

    attached_dir = paths.attachments_dir / "Attached Email.eml"
    assert paths.eml_file.exists()
    assert (paths.attachments_dir / "top.txt").read_bytes() == b"top-data"
    assert (attached_dir / "original.eml").read_bytes().startswith(b"From:")
    assert (attached_dir / "body.txt").read_text(encoding="utf-8") == "Hello"
    assert (
        attached_dir / "attachments" / "invoice.pdf"
    ).read_bytes() == b"pdf-bytes"
