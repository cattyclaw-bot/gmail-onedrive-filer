from datetime import datetime
from pathlib import Path

from gmail_onedrive_filer.filer import build_message_paths, sanitize_component


def test_sanitize_component_removes_invalid_chars() -> None:
    value = 'hello<>:"/\\|?*world'
    assert sanitize_component(value) == "hello_________world"


def test_build_message_paths_uses_date_tree() -> None:
    root = Path("/tmp/onedrive")
    dt = datetime(2026, 3, 6, 12, 0, 0)
    paths = build_message_paths(root, dt, "Subject", "msg-1")
    assert "/2026/03/06/" in str(paths.base_dir)
    assert paths.eml_file.name == "original.eml"
