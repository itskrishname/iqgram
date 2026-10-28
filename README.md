# IQGram

**IQGram** is an experimental Python **Telegram MTProto transfer library**, not a Telegram bot application.

This repository contains a custom parallel download range scheduler, concurrent upload-part scheduler, a pluggable transport adapter, and a developer API for Telegram bot **and** user sessions. **It is not currently proven faster than WZGram**, and does not claim a 50x speedup. It uses **Telethon 1.45+ as the underlying authentication / MTProto RPC transport** while IQGram controls its file-part scheduling. It does **not** depend on WZGram.

> **Project status: experimental alpha 0.2.0.** Local unit tests pass; Telegram production integration and real-world 50x benchmarks have not been completed here. Do not ship high-value production data without independent Telegram testing.

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
        options=TransferOptions(download_workers=4, upload_workers=4),
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
TransferOptions(download_workers=4, upload_workers=4)
```

Workers are **concurrent scheduler tasks**, not guaranteed unique TCP connections. Telethon handles connections; these worker settings cannot guarantee better throughput. Valid range: 1–32. Telegram upload parts are 512 KiB, and downloads use 512 KiB aligned request chunks.

## Roadmap (not included yet)

1. Benchmark current WZGram, Telethon and IQGram transfer paths with reproducible VPS metrics.
2. Add dedicated media DC connection pooling in an independently implemented transport.
3. Add adaptive request pipelining and connection tuning based on measured RTT/throughput.
4. Implement a native Rust MTProto core with reviewed crypto, auth-key/session safety and CDN support.
5. Benchmark vs. WZGram under comparable conditions; ship speed claims **only** with independently reproducible results.

Telegram's documented transfer APIs allow 512 KiB upload parts, pipelined requests, and dedicated media sessions, but throughput remains constrained by account, datacenter, CPU, disk and real network capacity. A 1 Gbps line has a theoretical upper limit of 125 MB/s before overhead.

See [performance plan](docs/PERFORMANCE.md), [architecture](docs/ARCHITECTURE.md), and [tests](tests/).
