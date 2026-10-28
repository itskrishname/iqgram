# Changelog

## 0.2.0 — 2026-10-28

- Re-scoped IQGram as a **library**, not a bot application.
- Removed built-in bot commands, config.py, miko.py, queue and Docker bot service.
- Replaced WZGram transport dependency with a Telethon adapter and IQGram-owned concurrent chunk scheduling.
- Added installable SDK, tests, benchmarks and docs.
- Documented that the independent native Rust engine and 50x speed proof are not built.
