from gmail_onedrive_filer.cli import build_parser


def test_cli_parses_sync() -> None:
    parser = build_parser()
    args = parser.parse_args(["--root", "/tmp/od", "sync", "--max", "10"])
    assert args.command == "sync"
    assert args.max_results == 10


def test_cli_parses_plan() -> None:
    parser = build_parser()
    args = parser.parse_args(["--root", "/tmp/od", "plan", "--max", "5"])
    assert args.command == "plan"
    assert args.max_results == 5


def test_cli_parses_triage() -> None:
    parser = build_parser()
    args = parser.parse_args(["--root", "/tmp/od", "triage", "--max", "12"])
    assert args.command == "triage"
    assert args.max_results == 12
