# IQGram

**IQGram 0.1.0: runnable MTProto Telegram media transfer toolkit for bots and user accounts.**

IQGram implements its own Python client facade, SQLite queue, bot commands, throughput measurement and CLI. It **uses WZGram 3.1.1 as the actual Telegram MTProto transport** (including its Rust-based cryptography), rather than claiming that a new independent Rust/MTProto transport or a 50x performance breakthrough has been built.

## Included in this build

- Both bot-token and user-account authentication (different saved session files)
- Telegram media download, local document upload, Saved Messages support for users
- Per-operation progress and average MiB/s display
- CLI benchmark for download, and optional upload back to a chosen chat
- Admin-allowlisted Telegram bot with `/start`, `/help`, `/download`, `/mirror`, `/benchmark`, `/status`, `/cancel`, `/retry`, `/upload`
- SQLite WAL job queue with persisted jobs and configurable workers
- Cooperative active-transfer cancellation and no automatic replay of interrupted uploads
- Docker, Compose, `python3 miko.py`, tests and config.py settings

**Not yet supported:** Native custom Rust transport, guaranteed single-file 50x speedup, automatic byte-level resume for interrupted downloads or uploads, multi-VPS orchestration. IQGram's `MAX_CONCURRENT_TRANSMISSIONS` controls the number of concurrent file transfers at the underlying library level; it does not directly mean number of chunks per file.

## Ubuntu VPS installation

Run these commands after extracting the ZIP into `~/IQGram`:

```bash
mkdir -p ~/IQGram
cd ~/IQGram
unzip -o ~/IQGram-Full-Working-V1.zip
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Python 3.11+ required. On Ubuntu 24.04 Python 3.12 works. Run `pip install -e '.[fast]'` if you additionally want optional uvloop on Linux.

Edit the included **local** `config.py`:

```python
API_ID = 123456
API_HASH = 'your_32_character_api_hash_here'
BOT_TOKEN = 'your_bot_token_here'
ALLOWED_USER_IDS = '123456789'
DATA_DIR = './data'
MAX_CONCURRENT_TRANSMISSIONS = 8
QUEUE_WORKERS = 2
DELETE_AFTER_MIRROR = False
```

Get API ID/hash at https://my.telegram.org/apps, bot token from @BotFather. Use *your own values*; the placeholders are intentionally unusable. **Do not upload `config.py`, data, .session files, or secrets to GitHub**. They are excluded by `.gitignore` / `.dockerignore`. You may set uppercase environment variables instead; they take precedence.

Check setup:

```bash
python3 miko.py doctor
python3 miko.py login --account bot
python3 miko.py login --account user
```

The user login may prompt interactively for phone number, Telegram code and 2FA password, once. No browser or password stored in `config.py` is required. Sessions are saved in `data/sessions/` with restricted directory permissions; protect the VPS and its disk. Do not run multiple IQGram instances on the same session directory simultaneously.

## Start bot

```bash
python3 miko.py
```

Equivalent to `python3 miko.py bot`, after setting BOT_TOKEN and at least one `ALLOWED_USER_IDS` entry. Send your bot a media file, reply to it with `/benchmark` to download then send it back and report download/upload throughput. You can use `/download` for download only. Only allowlisted user IDs can command the bot.

Commands:

| Command | Behavior |
| --- | --- |
| `/start` `/help` | Show supported commands |
| `/download` (reply to media) | Queue download to `data/downloads` |
| `/mirror` (reply to media) | Queue download then upload a document back |
| `/benchmark` (reply to media) | Same as mirror, reports separate transfer rates |
| `/status` | Last 10 jobs and their progress |
| `/cancel 3` | Request cancellation; cooperative inside next progress callback |
| `/retry 3` | Restart a failed/interrupted transfer from the beginning |
| `/upload 3` | Upload the local file from completed job 3 into this chat |

**Important:** All bot downloads must be reply-based to media *the bot can actually access*. The bot cannot access arbitrary private channels by knowing a message ID alone. `/upload` may take as long as a file transfer and uses the client directly; other queue jobs remain in their workers.

## CLI transfer and benchmark

```bash
# Downloads a message using the user account
python3 miko.py download --account user --chat me --message 123

# Upload local file to Saved Messages
python3 miko.py upload --account user --chat me --file ./video.mkv

# Download throughput benchmark, without sending anything
python3 miko.py benchmark --account user --chat me --message 123

# Download + upload throughput (sends a new message)
python3 miko.py benchmark --account user --chat me --message 123 --upload-chat me

# Bot account to a channel it can access
python3 miko.py download --account bot --chat -1001234567890 --message 42
```

To obtain a message ID, inspect the source message link or Telegram client metadata. A private channel must grant appropriate access to the current account.

**Speed comparison:** benchmark the same file, VPS, account and time window against WZGram or other clients. 1 Gbps network theoretically corresponds to 125 MB/s before overhead, not guaranteed Telegram throughput. This build has not been live benchmarked against Telegram in the build environment.

## Docker

```bash
# After editing config.py on your VPS
sudo docker compose up -d --build
sudo docker compose logs -f iqgram
sudo docker compose down
```

To login a user with Docker, stop the bot service first and use an interactive container sharing the same named data volume, such as:

```bash
sudo docker compose stop iqgram
sudo docker compose run --rm -it iqgram python miko.py login --account user
sudo docker compose up -d
```

Never run interactive login and the running bot process using the same user session simultaneously.

## Python SDK

```python
import asyncio
from iqgram import Client

async def main():
    async with Client('user') as iq:
        path = await iq.download(chat_id='me', message_id=123, directory='./downloads')
        msg = await iq.upload(chat_id='me', filename=path)
        print(msg.id)

asyncio.run(main())
```

Configure `config.py` in the working directory or set env vars first. `Client.raw` exposes the underlying WZGram client for additional Telegram API methods.

## Tests

```bash
pip install -e '.[dev]'
pytest -q
python -m compileall -q iqgram miko.py
```

All included tests use local fakes for the Telegram transport (no Telegram credentials required). A live smoke test must be run on your own VPS/account. Distinguish validated local logic from verified real-world transfer speed.

## Security and reliability notes

- No secret API values in the public repository. Real `config.py` is ignored by Git.
- Access to bot commands is denied unless Telegram user ID is on the allowlist.
- User-requested `/upload` is confined to downloaded IQGram files. The CLI upload intentionally accepts any local file you specify.
- SQLite running jobs become `interrupted` on restart to prevent automatic duplicate uploads. `/retry` deliberately starts again and may duplicate a send if the original completed just before a crash.
- If a cancellation occurs, the client requests stop at its next progress callback; this is not an immediate network-level cancellation guarantee.
- The downloaded content and credentials remain on your VPS; keep storage secure and back it up appropriately.

## References and licensing

- WZGram docs: https://wzgram.com/intro/install/
- WZGram download: https://wzgram.com/api/methods/download_media/
- WZGram send document: https://wzgram.com/api/methods/send_document/
- WZGram cancellation: https://wzgram.com/api/methods/stop_transmission/

IQGram's own project code is MIT-licensed. WZGram is a separate LGPL-3.0-or-later dependency installed from PyPI and retains its own license.

## GitHub CI

`.github/workflows/tests.yml` runs the local unit tests on supported Python versions (3.11–3.13). It does **not** authenticate with Telegram or establish speed figures. Any live integration test must be conducted on an authorized account and network with separately managed secrets.
