# gmail-onedrive-filer

Save specific emails from Gmail into OneDrive.
Email filer that reads Gmail messages and files them into date-based folders
inside a local OneDrive-synced directory.

It will periodically need the Google token refreshed, see refresh section below.

## TODO
- check if refresh token can be done better, eg auto refresh
- make google app live, so we don't get warning


## Behavior
- Reads Gmail using the Gmail API (OAuth)
- Defaults to query: `label:stluke-tofile`
- Supports triage mode to find likely invoice emails from last 2 days and add `stluke-tofile`
  - Default triage query:
    - `newer_than:2d -label:stluke-filed -label:stluke-tofile ((subject:(invoice OR invoices OR invoicing OR expense OR expenses OR bill OR transfer OR order OR orders OR subscription OR "tax invoice" OR "invoice available" OR "payment receipt" OR "sales receipt" OR remittance OR payout OR renewed OR renewal OR renew) -subject:("single-use code" OR verify OR security OR "shared the folder" OR newsletter)) OR from:(stripe.com) OR from:(gocardless) OR (from:(lynette.polderman@hotmail.co.uk OR chriswarrell54@gmail.com) has:attachment))`
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
1. Create a Google Cloud OAuth Desktop app:
   - Go to: https://console.cloud.google.com/apis/credentials
   - Create Project (or use existing)
   - Click "Create Credentials" → "OAuth client ID"
   - Application type: "Desktop app"
   - Download the JSON, rename to `credentials.json`
2. Save credentials: `./secrets/google-credentials.json`
3. Install package:
   - `python3 -m pip install -e .`
4. First run (triggers OAuth browser flow):
   ```bash
   gmail-onedrive-filer --root "/path/to/OneDrive/EmailArchive" sync
   ```
   This opens a browser to sign in with Google. After auth, token is saved to `./secrets/google-token.json`.

## Google Token Refresh
This is like the first run above:

cd /home/openclaw/.openclaw/workspace/gmail-onedrive-filer
rm -f secrets/google-token.json
. .venv/bin/activate
gmail-onedrive-filer --root "/home/openclaw/OneDrive/EmailArchive 1" plan --max 1

This will give you a URL to open, do that, select the gmail account that is to be sync'd - eg stlukeselthampark@gmail.com

Select continue with the developer app, enable the permissions requested - read/write emails (its going to be adjusting labels)
It will then show an error page, "site can't be reached" - this is ok, copy the new url from the browser back into the terminal session we started above.
If all is good, it will print a bit of JSON, showing the plan

To confirm its ok, rerun the filer line and it should just print the plan again, namely:

gmail-onedrive-filer --root "/home/openclaw/OneDrive/EmailArchive 1" plan --max 1

Example plan response:
{
  "mode": "plan",
  "query": "label:stluke-tofile",
  "fetched": 0,
  "filed": 0,
  "skipped": 0,
  "planned_paths": [],
  "dual_label_fixes": 0
}


## OneDrive Reauth (abraunegg client)

The local `~/OneDrive/EmailArchive 1/` directory is kept in sync with OneDrive by the `abraunegg/onedrive` v2.5.10 client. Its bundled Microsoft `application_id` is broken for our account (interactive flow → `/common/wrongplace`, device flow → "code expired"), so we use a custom Entra app registration.

### Custom Entra app
- Portal: https://entra.microsoft.com → Identity → Applications → App registrations → `openclaw-onedrive`
- **Client (Application) ID**: `f4c55830-766f-403b-ab59-90b0241bfc24` (already pinned in `~/.config/onedrive/config` as `application_id = "..."`)
- **Supported account types**: Any Entra ID tenant + Personal Microsoft accounts
- **Allow public client flows**: **Yes** (Authentication → Advanced settings) — critical
- **Redirect URIs** (Mobile and desktop applications):
  - `https://login.microsoftonline.com/common/oauth2/nativeclient`
  - `http://localhost`
  - `https://login.live.com/oauth20_desktop.srf`
- **Microsoft Graph delegated permissions**: `Files.ReadWrite`, `Files.ReadWrite.All`, `Sites.ReadWrite.All`, `offline_access`, `User.Read` (all five required — `Files.ReadWrite.All` alone causes HTTP 400 invalidRequest on file uploads even though directory creation works, which is misleading)

### Reauth procedure
When the service starts crash-looping with `AADSTS70000: The user could not be authenticated`:

```bash
systemctl --user stop onedrive
onedrive --reauth     # interactive: opens browser, sign in as the OneDrive owner, paste back redirected URL
onedrive --sync --resync --verbose 2>&1 | tee /tmp/onedrive-resync.log
systemctl --user start onedrive
systemctl --user status onedrive --no-pager
```

`--resync` is required because the local state DB is invalidated whenever `application_id` changes (or after a long auth gap). It needs `--sync` (or `--monitor`) alongside it in v2.5.10.

### Gotchas
- abraunegg `--dry-run` is **not actually dry**: it creates remote directories for real and may issue real PUTs that get reported as 400s. Treat dry-run skeptically — if directories were created and only file uploads failed, the cause is usually missing scopes, not local state.
- Resync warning lists possible deletes/overwrites/conflicts, but in practice if the dry-run plan shows zero of those, the real run is safe.
- Watch out for false-positive "errors" in log greps: `£400.00` invoice amounts match `400` and look like HTTP 400s.

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
