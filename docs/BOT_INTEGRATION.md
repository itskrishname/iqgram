# Use IQGram inside an existing Telegram bot

IQGram is a Python **library**, not a replacement for your Telegram bot's commands, plugins, database or UI. Keep your existing bot and call IQGram only for media transfers. **The default remains 4 workers** for download and upload. Throughput is limited by your VPS, Telegram and datacenter routing; 50x is a performance *goal*, not a verified result.

## Install in the bot's existing Python environment

```bash
# After copying/extracting the IQGram source into ~/iqgram:
cd ~/your-existing-bot
source .venv/bin/activate
python -m pip install -e "$HOME/iqgram[fast]"
python -c 'from iqgram import Client, TransferOptions; print("IQGram import OK")'
```

If your bot doesn't use a venv, install IQGram into the interpreter that runs that bot. `pip install -e` is for local source; after you publish an accessible Git repo, you may use `pip install 'git+https://github.com/itskrishname/iqgram.git'`. Do not assume an unpublished repository is accessible. IQGram v0.5.1 requires Python >=3.11.

## Option A: Already using Telethon (best fit)

`Client.from_telethon(existing_telethon_client)` **shares your already-connected Telethon session**. It does not log in again, start or disconnect your existing bot. Your existing code controls shutdown. Do *not* call `from_telethon` with a Pyrogram/Aiogram client; those are different APIs.

```python
from pathlib import Path
from iqgram import Client as IQClient, TransferOptions

# `bot` is your existing, already-connected Telethon TelegramClient.
iq = IQClient.from_telethon(
    bot,
    options=TransferOptions(download_workers=4, upload_workers=4),
)

# In any async bot handler (with permission to read source chat):
result = await iq.download(source_chat, source_message_id, Path('/tmp/iqgram-file.mkv'))
print('Download MiB/s:', round(result.bytes_per_second / 1048576, 2))
sent = await iq.upload('/tmp/iqgram-file.mkv', destination_chat, media_kind='document')
print('Uploaded Telegram message ID:', sent.value.id)
```

For a complete admin-only `/iqcopy` reply-to-file example, see [`examples/integrate_existing_telethon_bot.py`](../examples/integrate_existing_telethon_bot.py). The example uses a temporary directory and checks an admin user ID; it is **demonstration code**, not a replacement for your bot.

**Important:** IQGram does not own the externally supplied client. Even `async with Client.from_telethon(bot)` will **not disconnect `bot`**. For a regular `Client(...)` that creates its own Telegram session, IQGram does disconnect it when the context exits.

## Option B: Pyrogram / Pyrofork / Aiogram / another framework

IQGram cannot reuse an existing Pyrogram/Pyrofork session object or Bot API HTTP connection directly. Run **one separately authenticated IQGram MTProto session**, once per bot process, and use that client from your existing handlers.

```python
import os
from iqgram import Client as IQClient, TransferOptions

# Once at your application's startup, not inside every bot update:
iq = IQClient(
    session='my_bot_iqgram',  # separate from Pyrogram/Pyrofork session
    api_id=int(os.environ['IQGRAM_API_ID']),
    api_hash=os.environ['IQGRAM_API_HASH'],
    bot_token=os.environ['IQGRAM_BOT_TOKEN'],
    options=TransferOptions(download_workers=4, upload_workers=4),
)
await iq.start()

# In an async handler:
result = await iq.download('@channel_you_control', 123, '/tmp/media.bin')
# Or upload an existing local file to a chat accessible to IQGram's account:
sent = await iq.upload('/path/to/local.mkv', '@your_destination', media_kind='document')

# Once at application shutdown:
await iq.close()
```

Run the IQGram client only once in each process; repeated logins can cause rate limits, conflict with shared `.session` files or slow performance. **Do not share session filenames between frameworks.** The IQGram MTProto session may not resolve chats that only the other bot framework knows. Both clients must have access to the relevant chat/message; Bot API `file_id` alone is **not** an IQGram `message_id`. Multiple bot sessions using the same token may have differing peer caches and update behavior; test this with your own chats before deployment.

Full reference examples:

- [`examples/integrate_pyrogram_companion.py`](../examples/integrate_pyrogram_companion.py) — Pyrogram / Pyrofork plus separate IQGram, admin-only `/iqtest` command to download from a known authorized source.
- [`examples/integrate_aiogram_companion.py`](../examples/integrate_aiogram_companion.py) — Aiogram 3 plus separate IQGram, admin-only `/iqtest` command.

For these two examples, set `IQGRAM_API_ID`, `IQGRAM_API_HASH`, `IQGRAM_BOT_TOKEN`, `IQGRAM_ALLOWED_USER_ID`, `IQGRAM_SOURCE_CHAT`, and `IQGRAM_SOURCE_MESSAGE_ID` as environment variables in the server. Use a public channel or an accessible Telegram chat as the source. Do not put real credentials into source files or Git.

## File type support and media behavior

```python
await iq.upload('/files/movie.mkv', '@destination', media_kind='document')
await iq.upload('/files/movie.mp4', '@destination', media_kind='video')
await iq.upload('/files/music.mp3', '@destination', media_kind='audio')
await iq.upload('/files/photo.jpg', '@destination', media_kind='photo')
await iq.upload('/files/voice.ogg', '@destination', media_kind='voice')
await iq.upload('/files/sticker.webp', '@destination', media_kind='sticker')
```

Arbitrary extensions work as generic Telegram documents. Native media types still require valid encoding, metadata and Telegram permission/size limits. IQGram cannot convert arbitrary file bytes into a Telegram poll, story, paid media or secret chat message.

## Progress callback and cancellation

```python
async def on_progress(status):
    # Application controls whether/when to edit a progress message.
    # IQGram already throttles callback events internally.
    print(status.direction, f'{status.percent:.1f}%',
          f'{status.bytes_per_second / 1048576:.2f} MiB/s')

result = await iq.download('@source', 123, '/tmp/media.bin', progress=on_progress)
```

Call IQGram's async methods from an async handler. Cancel the task with `task.cancel()`; propagate `asyncio.CancelledError` rather than swallowing it. Temporary download parts are cleaned on failures/cancellation. Avoid using synchronous `asyncio.run()` inside an already running bot event loop. Make destination paths unique per concurrent transfer and remove local files when finished.

If Telegram source and target both exist and the media is authorized/unprotected, `await iq.reuse_media(source_chat, message_id, target_chat)` may avoid downloading and reuploading entirely. It is a server-side media reference, **not evidence of higher network throughput**.

## Deployment / common errors

- `ModuleNotFoundError: iqgram`: install with the **same Python/venv** your bot uses.
- `Set IQGRAM_API_ID`: export environment variables in the bot's process manager or launch script; interactive terminal variables disappear after SSH reconnect.
- `Could not find the input entity`: IQGram's Telegram session cannot resolve/access this peer; ensure the account has access and resolve via the IQGram session's own dialogs.
- `database is locked`: two processes used the same session file. Give each process a distinct session path or ensure a single owner.
- `FileExistsError`: choose a unique download destination; IQGram refuses overwriting existing downloads.
- Telegram FloodWait, unavailable media, invalid bot permissions, native format validation failures: respect Telegram errors and account restrictions; do not retry in a tight loop.
- `asyncio.run() cannot be called from a running event loop`: keep IQGram startup/download/close inside your bot's existing async lifecycle.

**Performance:** This integration adds no guaranteed throughput improvement. The library currently uses Telethon for MTProto transport; WarpCrypto is optional/experimental and should only be enabled in a fresh process before connecting any Telethon session. Keep the default 4 workers unless your own controlled benchmarks justify changes.
