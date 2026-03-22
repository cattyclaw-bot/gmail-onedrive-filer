# gmail-onedrive-filer

echo "Remember to sign in to the account we emails filed - usually: stlukeselthampark@gmail.com"

cd /home/openclaw/.openclaw/workspace/gmail-onedrive-filer
rm -f secrets/google-token.json
. .venv/bin/activate
gmail-onedrive-filer --root "/home/openclaw/OneDrive/EmailArchive 1" plan --max 1


