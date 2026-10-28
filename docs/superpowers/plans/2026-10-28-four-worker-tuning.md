# IQGram Four-Worker Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Preserve four-worker defaults without hard cap and enable transport-efficient 4-worker benchmarking.

**Architecture:** Keep existing Python transfer scheduler. Make Client slot capacity configurable using current option values, and parameterize download chunk size independently of Telegram's fixed upload part size. Expose request size in CLI and describe measurements candidly.

**Tech Stack:** Python 3.11+, asyncio, Telethon 1.45, pytest.

**Spec:** docs/superpowers/specs/2026-10-28-four-worker-tuning-design.md

## Global Constraints
- 4 default upload and download workers, no hard-cap at four.
- Valid experimental range 1..32 workers; per-Client shared slots use configured max, default 4.
- Upload 512 KiB, download requests either 512 or 1024 KiB, default 512 KiB.
- No native engine or 50x speed claims.

## Review Focus
- Download with exact full-size chunk and a short final chunk produces byte-identical output.
- Raising workers above four in options must not secretly run only four jobs.
- Default four-worker concurrent transfers share only four backend slots.
- CLI rejects invalid request sizes with usage error; default remains 512 KiB.
- On failure the partial file is removed, even when using 1024 KiB chunks.

---

### Task 1: Remove hard cap without changing default
**Files:** Modify `src/iqgram/transfer.py`, `tests/test_four_worker_budget.py`.
**Interfaces:** `TransferOptions(download_workers=4, upload_workers=4, download_request_size=524288)`, `TransferEngine(...)._slots` configurable.
- [x] Write tests asserting worker 8 allowed and slot capacity used; existing default 4 shared budget tests preserved.
- [x] Run targeted tests and see expected FAIL.
- [x] Update validation to 1..32 and replace hardcoded semaphore with configured maximum.
- [x] Run targeted and complete test suites; record results.

### Task 2: Download requests configurable within MTProto limits
**Files:** Modify `src/iqgram/transfer.py`, `tests/test_engine.py`.
**Interfaces:** `TransferOptions.download_request_size: int` with allowed values `524288` and `1048576`.
- [x] Write tests for 1 MiB download, short final chunk, 512 KiB upload preserved, rejects nonstandard sizes.
- [x] Run failing tests.
- [x] Parameterize download-only chunk counts, offsets and backend iteration.
- [x] Run tests.

### Task 3: CLI exposure, documentation, release
**Files:** Modify `examples/benchmark.py`, `tests/test_benchmark_cli.py`, `README.md`, `docs/PERFORMANCE.md`, `CHANGELOG.md`, `src/iqgram/__init__.py`, `pyproject.toml`.
- [x] Write CLI tests for new request-size option and changed worker-count range; see failure.
- [x] Add argparse and TransferOptions keyword args; report active request size; verify tests.
- [x] Document controlled A/B 512/1024 benchmark on 4 workers and no guaranteed speedup.
- [x] Build wheel, fresh-extract ZIP, test imports and package, inspect for secrets.
