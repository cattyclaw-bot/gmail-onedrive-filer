# gmail-onedrive-filer

Email filer that reads Gmail messages and files them into date-based folders
inside a local OneDrive-synced directory.

## Planned behavior
- Read Gmail (all mail except spam/trash)
- File by received date (`YYYY/MM/DD`)
- Store each email in its own folder with:
  - `original.eml`
  - `body.txt`
  - `attachments/`
  - `metadata.json`

## Status
Scaffold created. Implementation in progress.
