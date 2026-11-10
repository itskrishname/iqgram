# IQGram

**IQGram** is an experimental Python **Telegram MTProto transfer library**, not a Telegram bot application.

This repository contains a custom parallel download range scheduler, concurrent upload-part scheduler, a pluggable transport adapter, and a developer API for Telegram bot **and** user sessions. **It is not currently proven faster than WZGram**, and does not claim a 50x speedup. It uses **Telethon 1.45+ as the underlying authentication / MTProto RPC transport** while IQGram controls its file-part scheduling. It does **not** depend on WZGram.

> **Project status: experimental alpha 0.5.1.** Local unit tests pass; Telegram production integration and real-world 50x benchmarks have not been completed here. Do not ship high-value production data without independent Telegram testing.


## v0.5.1 — Integrate IQGram into ANY existing async Telegram bot

Start with **[docs/BOT_INTEGRATION.md](docs/BOT_INTEGRATION.md)** for copy-paste installation, startup/shutdown and error handling. Run IQGram as a library; you do **not** need to replace your existing bot's handlers, plugins, database, menus or commands.

- **Existing Telethon bot:** call `Client.from_telethon(existing_connected_bot)`, share its MTProto connection and leave lifecycle ownership with the application. Example: [`examples/integrate_existing_telethon_bot.py`](examples/integrate_existing_telethon_bot.py).
- **Pyrogram / Pyrofork / Aiogram / another framework:** start one separate `Client('iqgram_companion', api_id, api_hash, bot_token=...)` at bot startup; close it once at shutdown. These frameworks cannot directly share their existing client object with IQGram. Examples: [`examples/integrate_pyrogram_companion.py`](examples/integrate_pyrogram_companion.py) and [`examples/integrate_aiogram_companion.py`](examples/integrate_aiogram_companion.py).
- **No framework lock-in:** from an async handler, `await iq.download(chat, message_id, path)` or `await iq.upload(path, chat, media_kind='document')`. Default workers remain 4.

Use only chats/messages accessible to IQGram's Telegram session. Do not share `.session` files between libraries. This release improves integration ergonomics, **not measured transfer speed**.


## v0.5.0 — File media, performance profiling and optional WarpCrypto

**File formats:** IQGram transfers **arbitrary binary files** (MKV, MP4, PDF, ZIP, 7z, APK, EXE, TXT, SRT, FLAC, WEBM, TGS, WEBP and any extension) as Telegram *documents*. When you want Telegram-native semantics, select `media_kind` explicitly:

```python
# Default remains a document to preserve existing integrations.
await client.upload('any-file.7z', 'me')
await client.upload('photo.jpg', 'me', media_kind='photo')
await client.upload('movie.mp4', 'me', media_kind='video')
await client.upload('song.mp3', 'me', media_kind='audio')
await client.upload('voice.ogg', 'me', media_kind='voice')
await client.upload('circle.mp4', 'me', media_kind='video_note')
await client.upload('funny.gif', 'me', media_kind='animation')
await client.upload('sticker.webp', 'me', media_kind='sticker')
await client.upload('picture.jpg', 'me', media_kind='auto')
```

The `auto` setting chooses native photos, MP4 video and common audio, while unknown extensions remain documents. Telegram may reject native types with invalid codecs, dimensions, missing metadata or account-specific restrictions. Sending *any bytes as a document* is distinct from creating valid Telegram *stickers, stories, polls or paid media*. Non-file messages remain accessible through `client.raw` where Telethon/Telegram support them. **Secret chats and DRM/protected content are not unlocked or bypassed.**

**Server-side reuse** can be much faster for moving an *already Telegram-hosted, unprotected* photo/document between permitted chats because it does not download or upload the bytes through the VPS:

```python
sent = await client.reuse_media('source_chat', 123, 'destination_chat', caption='Copied')
print(sent.id)
```

This is a server-side reference, **not** evidence of higher upload/download bandwidth. The source account must have access and Telegram may expire file references.

**4-worker diagnostic benchmark** (download-only; no new message sent):

```bash
python examples/benchmark.py \
  --session "$HOME/.iqgram_sessions/benchmark" \
  --chat me --message 7552 \
  --download-workers 4 --download-request-kib 1024 \
  --profile-download
```

Worker `iterator_wait` includes time waiting for network, library buffering and sender scheduling; it is **not raw TCP RTT**. `disk_write` includes thread scheduling overhead. Values overlap between workers. Use them to narrow suspected bottlenecks, not as exact network traces.

**Experimental WarpCrypto** is explicitly optional and process-wide. Do not activate it in a process already running Telethon sessions; it patches Telethon's AES-IGE helper at startup only *after* checking multiple ciphertext vectors against the existing crypto implementation. The default remains Cryptg. Use `pip install -e '.[fast,dev,warpcrypto]'` (or `pip install WarpCrypto`) then:

```bash
python examples/benchmark.py \
  --session "$HOME/.iqgram_sessions/benchmark" --chat me --message 7552 \
  --download-workers 4 --download-request-kib 1024 \
  --crypto warpcrypto --profile-download
```

This tests WarpCrypto **without modifying a live Telegram session database or hiding failed compatibility checks**. A faster AES primitive does *not* imply a 50× file transfer improvement. The runtime test of the actual WarpCrypto wheel and Telegram transfer must be performed on the owner's VPS; it was not available in the offline build environment.

**VPS upgrade:** Upload `IQGram-v0.5.0-Media-and-Profiler.zip` to `/root/`, then:

```bash
cd ~/iqgram
unzip -o ~/IQGram-v0.5.0-Media-and-Profiler.zip -d ~/iqgram
source .venv/bin/activate
python -m pip install -e '.[fast,dev,warpcrypto]'
python -m pytest -q
```

This archive contains source files only; it does not contain or erase `~/.iqgram_sessions/` or `.venv/`. Back up the existing source first if you have locally edited it.

---

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

## Opt-in 8/16 configuration (Pyrogram companion)

The included `examples/integrate_pyrogram_companion.py` uses these explicit
settings for the requested faster/concurrent-operation trial:

```python
pyrogram_bot = PyrogramClient(
    'example_pyrogram', api_id, api_hash, bot_token=token,
    workers=8, max_concurrent_transmissions=16,
)
iq = IQClient(
    'example_iqgram_companion', api_id, api_hash,
    bot_token=token, options=TransferOptions(download_workers=8, upload_workers=8),
)
```

`workers=8` configures Pyrogram handler workers;
`max_concurrent_transmissions=16` limits **Pyrogram's own** simultaneous file
transfers. These **do not** configure IQGram's Telethon transfer engine.
IQGram has its own `download_workers=8` / `upload_workers=8` for this example.
The standalone `examples/basic.py` also opts into 8 IQGram transfer workers.

**Library defaults remain four** for backwards compatibility and to preserve
prior measured benchmarks. The number 16 is *not* an IQGram upload RPC
pipeline depth or a promised speed multiplier. Higher concurrency may increase
memory usage, API rate limits, and contention; benchmark on your own VPS.
For the benchmark CLI, opt in with
`--download-workers 8 --upload-workers 8`.

## Settings

```python
TransferOptions(download_workers=4, upload_workers=4, download_request_size=524288, upload_pipeline_depth=1)
```

Workers are **concurrent scheduler tasks**, not guaranteed unique TCP connections. Every `Client` defaults to **4 active transfer slots total** shared between simultaneous downloads and uploads. The shared concurrency is derived from `max(download_workers, upload_workers)` rather than being hard-coded to 4. Valid worker values are 1–32, but there is **no special four-worker ceiling**. Increasing workers was slower on the owner's single 8-worker experiment; **the recommended and measured setup remains exactly 4 download and 4 upload workers**. These two figures refer to separate operations, not eight simultaneous TCP connections. Telethon manages its network connections.

With `upload_pipeline_depth=1` (default), four upload workers have four outstanding upload RPCs maximum. With experimental `upload_pipeline_depth=2`, the same four logical workers can have **up to eight requests in-flight**; depth=4 can reach sixteen. These are RPCs, not extra workers or guaranteed separate TCP connections. Memory stays bounded (approximately workers × depth × 512 KiB of part payloads plus overhead). Telegram may still throttle requests.

Telegram upload part size is fixed at 512 KiB. Download request size is 512 KiB by default, with an **optional experimental 1 MiB** mode. This changes the payload size requested per download RPC, **not** the number of workers or upload part size. No speedup has been verified for this mode yet.

## Four-worker speed tuning (v0.3.1)

- **Default:** four workers for download and four for upload; the default per-client shared backend-call budget is four.
- **No 4-worker hard cap:** other values are accepted for developers, but four is the performance optimization target.
- **A/B testing:** compare 512 KiB and 1024 KiB download RPC requests while keeping **four workers** in both cases. This helps identify whether RPC size is a limiting factor.
- **Telegram socket note:** four scheduler tasks do **not** imply four dedicated MTProto media-only TCP connections. Building an independent media session pool remains future engineering work.
- **Security:** `IQGRAM_API_ID` and `IQGRAM_API_HASH` are read by the *example benchmark only*. The library accepts credentials in `Client(...)` and has no `config.py`.

For upgrading to the *historic* v0.4.0 release, use the commands under the **v0.4.0 experimental** heading below; the v0.3.1 archive is superseded.

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

## Four-worker upload RPC pipelining (v0.4.0 experimental)

IQGram v0.4.0 adds **optional request pipelining inside each of the four existing upload workers**. This follows Telegram's documented local call queue guidance, without pretending that the extra requests equal more TCP connections. Defaults are intentionally unchanged until a real VPS test proves the new mode is faster.

**Upgrade existing `~/iqgram` folder (lowercase):**

```bash
cd ~/iqgram
unzip -o ~/IQGram-Four-Worker-Pipeline-v0.4.0.zip -d ~/iqgram
source .venv/bin/activate
python -m pip install -e '.[fast,dev]'
python -m pytest -q
```

Do not upload a virtualenv or Telegram `.session` file into GitHub. Environment credentials are not packaged. If SSH was reconnected, export `IQGRAM_API_ID` and `IQGRAM_API_HASH` locally again before benchmarking. Use a file you are authorized to transfer.

**Stable baseline: depth=1, 4 workers:**

```bash
python examples/benchmark.py \
  --session "$HOME/.iqgram_sessions/benchmark" \
  --chat me --message 7552 --upload-chat me \
  --download-workers 4 --upload-workers 4 \
  --download-request-kib 1024 --upload-pipeline-depth 1
```

**Experimental: depth=2, *still 4 workers*:**

```bash
python examples/benchmark.py \
  --session "$HOME/.iqgram_sessions/benchmark" \
  --chat me --message 7552 --upload-chat me \
  --download-workers 4 --upload-workers 4 \
  --download-request-kib 1024 --upload-pipeline-depth 2
```

Both commands transfer the same single ~1.38 GiB file and upload a new Saved Messages copy. The download algorithm is unchanged; compare **upload MB/s only** for this new feature. Run depth=1 and depth=2 on different rounds, ideally three each in alternating order; compare median throughput and respect any Telegram `FloodWait`. If the new depth is slower, use depth=1. `upload_pipeline_depth` is validated as 1–4 and is passed through `TransferOptions` for library users.

The screenshot claiming thousands of MB/s cannot be validated from screenshot alone. For reference a 1 Gbps VPS is limited to 125 MB/s before overhead, and 1623.32 MB / 78 s = 20.81 MB/s aggregate. IQGram measures **acknowledged bytes divided by wall-clock time**, never sums instantaneous speeds of parallel uploads.

## Roadmap (not included yet)

1. Benchmark current WZGram, Telethon and IQGram transfer paths with reproducible VPS metrics.
2. Add dedicated media DC connection pooling in an independently implemented transport.
3. Instrument request RTT, TCP retransmits, CPU/crypto and network idle time.
4. Consider native Rust MTProto transport only after profiling shows the bottleneck.
5. Benchmark vs. WZGram under comparable conditions; ship speed claims **only** with independently reproducible results.

Telegram's documented transfer APIs allow 512 KiB upload parts, pipelined requests, and dedicated media sessions, but throughput remains constrained by account, datacenter, CPU, disk and real network capacity. A 1 Gbps line has a theoretical upper limit of 125 MB/s before overhead.

See [performance plan](docs/PERFORMANCE.md), [architecture](docs/ARCHITECTURE.md), and [tests](tests/).
