# 0.5.1 — reusable bot integration (2026-11-07)

- Added public `Client.from_telethon(existing_connected_client, options=...)` to share an existing Telethon bot/user session without logging in or disconnecting its application-owned session.
- Added complete integration cookbook (`docs/BOT_INTEGRATION.md`) including startup/shutdown, 4-worker media transfers, progress, supported media types, error handling and session safety.
- Added runnable admin-only example bots showing Telethon in-process reuse and separate MTProto companion clients for Pyrogram/Pyrofork and Aiogram 3.
- No changes to IQGram's worker scheduling, media logic, transport backend, or measured transfer-speed claims. 50x real throughput remains unverified.

# 0.5.0 — media types, profiling and optional WarpCrypto (2026-11-07)

- Added explicit native upload modes (`document`, `auto`, `photo`, `video`, `audio`, `voice`, `video_note`, `animation`, `sticker`) while preserving document as the backwards-compatible default. Arbitrary file extensions remain supported as generic documents.
- Added Telethon fallback for photo/document download with unknown size and atomic no-overwrite output.
- Removed avoidable copies of Telethon memoryview download chunks; added per-worker iterator-wait and disk-write profiler and `--profile-download` benchmark option; no fabricated RTT or throughput claims.
- Added `Client.reuse_media` to send unprotected Telegram-hosted media without redundant VPS transfer.
- Added optional process-global WarpCrypto AES-IGE backend (`--crypto warpcrypto`) with ciphertext compatibility selftests; default remains Cryptg. **Not independently live-tested on VPS**.
- Kept four workers as the default and experimental upload pipeline depth configurable; no 4-worker hard cap.
- No guarantee or claim of 50x faster real Telegram file transfers.

# Changelog

## 0.4.0 — 2026-10-28

- Added optional bounded upload part RPC pipelining **within** the default four worker loops (`upload_pipeline_depth=1..4`, default 1).
- Each part counts toward upload progress only after server ACK; errors and cancellation drain outstanding tasks and do not publish incomplete media.
- Preserved the stable depth=1 path and shared logical worker budget across simultaneous jobs.
- Added `--upload-pipeline-depth` to standalone benchmarking CLI.
- 4-worker 50x goal remains **unverified**; do not confuse aggregate file/bot rates or per-part averages with single-file throughput.


## 0.3.1 — 2026-10-28

- Removed v0.3.0's hard four-worker maximum; four remains the **default and tuning target**, with 1–32 configurable workers.
- Shared per-client transfer slots now scale with configured concurrency, while remaining four by default.
- Download requests now optionally use 1 MiB chunks (`--download-request-kib 1024`) at the same four workers, preserving the 512 KiB baseline by default.
- Kept the protocol-required 512 KiB upload part size unchanged; all performance results require live rebenchmarking.
- Added tests covering configurable concurrency, exact file reconstruction and failed-transfer cleanup for 1 MiB download mode.

## 0.3.0 — 2026-10-28

- Default remains four workers for uploads and downloads; hard maximum is now four (previously 32).
- Add a single shared four-slot transfer budget per Client across overlapping downloads and uploads.
- Reject >4 workers early in the example benchmark with clear CLI help.
- Include measured user-supplied v0.2.0 results in performance docs; no unverified new speed claims.
- Keep bot/user session SDK, live Telethon transport and source library structure intact.

## 0.2.0 — 2026-10-28

- Re-scoped IQGram as a **library**, not a bot application.
- Removed built-in bot commands, config.py, miko.py, queue and Docker bot service.
- Replaced WZGram transport dependency with a Telethon adapter and IQGram-owned concurrent chunk scheduling.
- Added installable SDK, tests, benchmarks and docs.
- Documented that the independent native Rust engine and 50x speed proof are not built.
