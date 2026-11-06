# Four-Worker RPC Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable safe, opt-in upload request pipelining without adding worker loops or altering default behavior.

**Architecture:** Four long-lived upload workers each own a bounded queue of up to `upload_pipeline_depth` in-flight `save_part` tasks; acknowledgements update real byte counters. Per-Client shared worker budget stays at configured worker count, while an internal worker may have multiple RPCs outstanding.

**Tech Stack:** Python 3.11 asyncio TaskGroup, Telethon 1.45 adapter, pytest.

**Spec:** `docs/superpowers/specs/2026-10-28-four-worker-pipeline.md`

## Global Constraints
- No hard-coded four worker maximum; four worker default.
- Upload chunk fixed at 512KiB, count only server-acknowledged bytes.
- Do not ship credentials or sessions.

## Review Focus
- Nonblocking failures of any in-flight part prevent media publishing.
- Cancellation closes all in-flight tasks.
- Multi-job shared four-worker budget remains correct.
- Depth=1 retains existing throughput behavior and API compatibility.
- Depth 2/4 bounded memory; negative, boolean, enormous values rejected.

## Task 1: Pipeline protocol and behavior
- [ ] Add failing tests for 4 workers × 2 slots; depth=1; bounds, failure, cancellation.
- [ ] Run new tests and confirm failing assertions.
- [ ] Implement `upload_pipeline_depth` and bounded in-flight part tasks in `src/iqgram/transfer.py`.
- [ ] Run new and existing tests, verify all pass.

## Task 2: CLI and benchmark accuracy
- [ ] Add CLI tests for `--upload-pipeline-depth` (defaults 1, range 1-4).
- [ ] Run tests red.
- [ ] Add benchmark option and clear throughput reporting in `examples/benchmark.py`.
- [ ] Run all tests green.

## Task 3: Release and verification
- [ ] Update README, changelog, performance methodology, version metadata.
- [ ] Package source ZIP without cache, secrets, session, `.venv`.
- [ ] Verify archive extraction, source code compilation and pytest.
- [ ] Report exact tests and limitations (no live speed guarantee).
