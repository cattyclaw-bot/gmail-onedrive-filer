# gmail-onedrive-filer

Email filer that reads Gmail messages and files them into date-based folders
inside a local OneDrive-synced directory.

## Behavior
- Reads Gmail using the Gmail API (OAuth)
- Defaults to query: `label:stluke-tofile`
- Supports triage mode to find likely invoice emails from last 2 days and add `stluke-tofile`
  - Default triage query:
    - `newer_than:2d -label:stluke-filed -label:stluke-tofile ((subject:(invoice OR invoices OR expense OR expenses OR order OR orders OR subscription OR "tax invoice" OR "invoice available" OR "payment receipt" OR remittance OR payout) -subject:("single-use code" OR verify OR security OR "shared the folder" OR newsletter)) OR from:(stripe.com) OR from:(gocardless) OR (from:(lynette.polderman@hotmail.co.uk OR chriswarrell54@gmail.com) has:attachment))`
  - Versioned backup: `config/triage-rules.md`
- Files by internal received date: `YYYY/MM/DD`
- Stores each message in its own folder with:
  - `original.eml`
  - `body.txt`
  - `attachments/`
  - `metadata.json`
- Top-level attached emails (`.eml` / `message/rfc822`) are expanded one level:
  - each becomes a folder under parent `attachments/`
  - with its own `original.eml`, `body.txt`, `attachments/`, `metadata.json`
  - nested attached emails inside those are kept as files (not recursively expanded)
- After successful filing:
  - removes label `stluke-tofile` (if present)
  - adds label `stluke-filed`
  - adds year label from received date (for example `2026`)
  - removes `INBOX` label (archives from Inbox)

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

Triage likely invoice/bill emails from last 2 days and add `stluke-tofile`:

```bash
gmail-onedrive-filer --root "/path/to/OneDrive/EmailArchive" triage --max 100
```
