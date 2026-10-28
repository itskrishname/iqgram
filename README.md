# IQGram

**IQGram** is an experimental Python **Telegram MTProto transfer library**, not a Telegram bot application.

This repository contains a custom parallel download range scheduler, concurrent upload-part scheduler, a pluggable transport adapter, and a developer API for Telegram bot **and** user sessions. **It is not currently proven faster than WZGram**, and does not claim a 50x speedup. It uses **Telethon 1.45+ as the underlying authentication / MTProto RPC transport** while IQGram controls its file-part scheduling. It does **not** depend on WZGram.

> **Project status: experimental alpha 0.3.1.** Local unit tests pass; Telegram production integration and real-world 50x benchmarks have not been completed here. Do not ship high-value production data without independent Telegram testing.

## What belongs in the library?

- `src/iqgram/client.py` — reusable Python SDK (`Client`), bot/user sessions
- `src/iqgram/transfer.py` — independently implemented parallel chunk scheduler, progress and transfer validation
- `src/iqgram/telethon_adapter.py` — narrow bridge to an existing MTProto stack; replaceable by a Rust/raw-MTProto backend
- `examples/` — isolated scripts for developers, *not* built-in bot commands
- `tests/` — local tests for the scheduler and adapter

**Not included (by design):** `miko.py`, `config.py`, `/start` bot, Procfile, SQLite queue, forced channel bindings, Docker bot deployment, admin panel, stored secrets. Client applications manage those concerns themselves.

## Install from this repository

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[fast,dev]'
python -m pytest -q
```

Alternatively, after this repo is published to GitHub:

```bash
pip install 'git+https://github.com/itskrishname/iqgram.git'
```

If the repo is private, configure Git authentication on your own machine. Do not commit tokens, authentication session databases or `.env` files.

## Use it in your own application

```python
import asyncio
from iqgram import Client, TransferOptions

async def main():
    async with Client(
        'my_user_session', api_id=123456,
        api_hash='YOUR_API_HASH',
        options=TransferOptions(download_workers=4, upload_workers=4, download_request_size=524288),
    ) as client:
        result = await client.download('me', 100, 'video.mkv')
        print(f'Download: {result.bytes_per_second / 1048576:.2f} MiB/s')
        uploaded = await client.upload('video.mkv', 'me')
        print('Sent:', uploaded.value.id)

asyncio.run(main())
```

**For bots**, pass `bot_token='...'` to `Client` in the application's code, and only use a channel/chat it has permission to access. **For users**, omit `bot_token`; Telethon starts a user login flow if there is no saved session. Never share `.session` files. `client.raw` exposes the underlying Telethon client for other operations and authentication internals.

You can install IQGram with a project-specific account session name and pass in parameters directly. **The library does not load an application-level `config.py`.**

## Test on your VPS

Create your own session and export the credentials locally (do **not** commit them):

```bash
export IQGRAM_API_ID='YOUR_API_ID'
export IQGRAM_API_HASH='YOUR_API_HASH'
# Only for bot mode, if desired:
# export IQGRAM_BOT_TOKEN='YOUR_BOT_TOKEN'

python examples/benchmark.py --chat me --message 123 --upload-chat me
```

`--chat me` works for a **user account**. For a bot, provide a chat ID the bot can access. Use a 100 MiB–2 GiB document message and compare the same account, file, VPS and time window against WZGram. Benchmark three or more runs and compare medians. Upload benchmarking **sends a new message** to `--upload-chat`.

Only use media you are authorized to access. The code checks chunk lengths, avoids silently overwriting downloaded files and cleans incomplete download files on errors/cancellation.

## Settings

```python
TransferOptions(download_workers=4, upload_workers=4, download_request_size=524288)
```

Workers are **concurrent scheduler tasks**, not guaranteed unique TCP connections. Every `Client` defaults to **4 active transfer slots total** shared between simultaneous downloads and uploads. The shared concurrency is derived from `max(download_workers, upload_workers)` rather than being hard-coded to 4. Valid worker values are 1–32, but there is **no special four-worker ceiling**. Increasing workers was slower on the owner's single 8-worker experiment; **the recommended and measured setup remains exactly 4 download and 4 upload workers**. These two figures refer to separate operations, not eight simultaneous TCP connections. Telethon manages its network connections.

Telegram upload part size is fixed at 512 KiB. Download request size is 512 KiB by default, with an **optional experimental 1 MiB** mode. This changes the payload size requested per download RPC, **not** the number of workers or upload part size. No speedup has been verified for this mode yet.

## Four-worker speed tuning (v0.3.1)

- **Default:** four workers for download and four for upload; the default per-client shared backend-call budget is four.
- **No 4-worker hard cap:** other values are accepted for developers, but four is the performance optimization target.
- **A/B testing:** compare 512 KiB and 1024 KiB download RPC requests while keeping **four workers** in both cases. This helps identify whether RPC size is a limiting factor.
- **Telegram socket note:** four scheduler tasks do **not** imply four dedicated MTProto media-only TCP connections. Building an independent media session pool remains future engineering work.
- **Security:** `IQGRAM_API_ID` and `IQGRAM_API_HASH` are read by the *example benchmark only*. The library accepts credentials in `Client(...)` and has no `config.py`.

### Upgrade in place (VPS)

Download the ZIP and upload it to your VPS home directory, then run:

```bash
cd ~/IQGram
unzip -o ~/IQGram-Four-Worker-Tuning-v0.3.1.zip -d ~/IQGram
source .venv/bin/activate
python -m pip install -e '.[fast,dev]'
python -m pytest -q
```

The archive has files directly at the project root (no `IQGram-main/` nested folder). Your `.venv` and session files stay untouched. Do not commit `.session` files or exported credentials. This ZIP is a **source update**, not a GitHub push.

### Test the same file with four workers (two download RPC sizes)

**Known baseline, 512 KiB download requests:**

```bash
python examples/benchmark.py \
  --session "$HOME/.iqgram_sessions/benchmark" \
  --chat me --message 7552 --upload-chat me \
  --download-workers 4 --upload-workers 4 \
  --download-request-kib 512
```

**Experimental 1 MiB download requests, still four workers:**

```bash
python examples/benchmark.py \
  --session "$HOME/.iqgram_sessions/benchmark" \
  --chat me --message 7552 --upload-chat me \
  --download-workers 4 --upload-workers 4 \
  --download-request-kib 1024
```

Only download request size changes between the two commands. Upload uses the same 512 KiB parts and four upload workers in both cases, so don't expect an upload speedup from this setting. Repeat each mode under comparable VPS/network load, compare medians, and stop on any Telegram rate-limit error.

Your VPS may need `IQGRAM_API_ID` and `IQGRAM_API_HASH` exported again after SSH reconnect; the sample does not save them. The benchmark creates a new message in Saved Messages when `--upload-chat me` is supplied.

## Roadmap (not included yet)

1. Benchmark current WZGram, Telethon and IQGram transfer paths with reproducible VPS metrics.
2. Add dedicated media DC connection pooling in an independently implemented transport.
3. Add adaptive request pipelining and connection tuning based on measured RTT/throughput.
4. Implement a native Rust MTProto core with reviewed crypto, auth-key/session safety and CDN support.
5. Benchmark vs. WZGram under comparable conditions; ship speed claims **only** with independently reproducible results.

Telegram's documented transfer APIs allow 512 KiB upload parts, pipelined requests, and dedicated media sessions, but throughput remains constrained by account, datacenter, CPU, disk and real network capacity. A 1 Gbps line has a theoretical upper limit of 125 MB/s before overhead.

See [performance plan](docs/PERFORMANCE.md), [architecture](docs/ARCHITECTURE.md), and [tests](tests/).
