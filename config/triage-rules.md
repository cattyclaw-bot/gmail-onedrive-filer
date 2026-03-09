# St Luke Triage Rules

This file is the backup copy of triage rules used by `gmail-onedrive-filer triage`.

## Default Gmail Query

```text
newer_than:2d -label:stluke-filed -label:stluke-tofile ((subject:(invoice OR invoices OR expense OR expenses OR bill OR order OR orders OR subscription OR "tax invoice" OR "invoice available" OR "payment receipt" OR remittance OR payout) -subject:("single-use code" OR verify OR security OR "shared the folder" OR newsletter)) OR from:(stripe.com) OR from:(gocardless) OR (from:(lynette.polderman@hotmail.co.uk OR chriswarrell54@gmail.com) has:attachment))
```

## Included Criteria

- Subject contains invoice-style terms: `invoice`, `invoices`, `expense`, `expenses`, `order`, `orders`, `subscription`, `tax invoice`, `invoice available`, `payment receipt`, `remittance`, `payout`.
- Sender domain matches: `stripe.com`.
- Sender matches: `gocardless`.
- Sender matches either `lynette.polderman@hotmail.co.uk` or `chriswarrell54@gmail.com` and message has an attachment.

## Excluded Criteria

- Subject contains: `single-use code`, `verify`, `security`, `shared the folder`, `newsletter`.

## Labeling Behavior

- Triage adds `stluke-tofile`.
- Triage removes `INBOX` to archive triaged messages.
- Filing adds `stluke-filed` and year label (e.g. `2026`), removes `stluke-tofile`, and removes `INBOX`.
