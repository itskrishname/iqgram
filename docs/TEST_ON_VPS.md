# IQGram VPS live test checklist

Local automated tests prove the IQGram orchestration code and transfer API contracts, not a real Telegram connection. Run these real tests **after** filling credentials in `config.py`:

## 1. Dependencies and account login

```bash
python3 miko.py doctor
python3 miko.py login --account bot
python3 miko.py login --account user
```

A user account may ask for Telegram login code and 2FA password during first login. Keep the generated `data/sessions` files private. Both logins should display your Telegram identity.

## 2. Download

Send a 20-100 MiB document to your own Saved Messages (user account). Get that document's message ID from the message link/details. Then run:

```bash
python3 miko.py download --account user --chat me --message YOUR_MESSAGE_ID
```

Confirm the file is saved under `data/downloads/cli` and its file size matches Telegram's original.

## 3. Download + upload speed

```bash
python3 miko.py benchmark --account user --chat me --message YOUR_MESSAGE_ID --upload-chat me
```

This explicitly posts a **new** document to Saved Messages; don't use a public group accidentally. Record `download_mib_s` and `upload_mib_s` from its JSON output. Repeat 3 times and compare median speeds on the same VPS and account, including WZGram's direct API as a baseline.

## 4. Bot commands

Run `python3 miko.py bot` with `ALLOWED_USER_IDS` set, send a media file to the bot and reply `/download`, `/mirror`, `/benchmark`. Use `/status`, `/cancel JOB_ID`, `/retry JOB_ID` to validate queue controls.

## 5. Failure paths

- Use a message ID that doesn't exist: expect clear failure, never success.
- Try the same bot from a Telegram user ID not in the allowlist: expect access denied.
- Kill the bot during upload and restart: running jobs should report interrupted, not be automatically re-sent.
- Try `/upload` for a file outside IQGram's downloads folder: must be rejected.

## 6. Actual performance limitations

Performance depends on VPS routing, Telegram DC, session identity, file size, CPU and Telegram restrictions. A network rated at 1 Gbps does not guarantee 100 MB/s to Telegram. This V1 relies on WZGram's existing optimized MTProto layer, not a custom native 50x transfer engine.
