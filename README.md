# gmail-onedrive-filer

Email filer that reads Gmail messages and files them into date-based folders
inside a local OneDrive-synced directory.

## Behavior
- Reads Gmail using the Gmail API (OAuth)
- Defaults to query: `-in:spam -in:trash`
- Files by internal received date: `YYYY/MM/DD`
- Stores each message in its own folder with:
  - `original.eml`
  - `body.txt`
  - `attachments/`
  - `metadata.json`

## Setup
1. Create a Google Cloud OAuth Desktop app and download `credentials.json`.
2. Save credentials (example): `./secrets/google-credentials.json`
3. Install package:
   - `python3 -m pip install -e .`

On first run, a browser OAuth flow opens and writes token JSON to
`./secrets/google-token.json` by default.

## Usage
Manual sync:

```bash
gmail-onedrive-filer --root "/path/to/OneDrive/EmailArchive" sync
```

Backfill with date bounds:

```bash
gmail-onedrive-filer --root "/path/to/OneDrive/EmailArchive" backfill --since 2025/01/01 --until 2026/01/01
```

Dry run:

```bash
gmail-onedrive-filer --root "/path/to/OneDrive/EmailArchive" --dry-run sync --max 50
```

Plan output paths only (no message body/attachment fetch, no writes):

```bash
gmail-onedrive-filer --root "/path/to/OneDrive/EmailArchive" plan --max 50
```
