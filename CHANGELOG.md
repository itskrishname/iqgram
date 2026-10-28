# IQGram changelog

## 0.1.0 — 2026-10-28

- First actual runnable Python distribution, `iqgram` CLI and `miko.py` entrypoint.
- Account-isolated bot and user authentication via WZGram.
- Media download/upload, CLI benchmarks and progress reporting.
- Telegram bot commands, persistent SQLite queue, retry and cooperative cancellation.
- Docker, Compose, packaging, tests and initial security controls.
- Scope boundary: backend remains WZGram, not a new custom Rust implementation. Live network performance remains unverified until tested on a Telegram account.
- Regression coverage for incomplete post-upload cleanup and shutdown/cancel status handling.
