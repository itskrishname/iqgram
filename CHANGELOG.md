# Changelog

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
