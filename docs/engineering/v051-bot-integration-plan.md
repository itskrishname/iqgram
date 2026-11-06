# IQGram 0.5.1: bot integration design and verification

Goal: Enable users to integrate IQGram's media transfer Client in an existing async Telegram bot without replacing their existing handlers or storing secrets in the library.

Chosen approach: public `Client.from_telethon(...)` adapter for already-connected Telethon clients, plus a documented separate IQGram session for Pyrogram/Pyrofork/Aiogram and other frameworks. This avoids adding framework-specific dependencies to the library. Alternatives considered: (a) monkeypatch each bot framework's internal transfer engine (fragile, rejected); (b) rebuild bots around IQGram (not library-only, rejected).

Constraints: Four transfer workers by default; no hard four-worker cap; no unverified speed improvements; do not take ownership of externally supplied Telethon session; no bot token/API hash in sources.

Verification steps:

1. Regression test that `from_telethon` accepts an existing Telethon-compatible client, reuses it for download and does not start/disconnect it.
2. Negative tests for missing and non-Telethon clients.
3. Regression test that ordinary bot-token `Client` still starts/disconnects owned sessions.
4. Add framework-independent usage documentation and runnable admin-only examples.
5. Run entire existing suite and compile examples.
6. Package source ZIP and run full tests from a fresh extraction.

No live Telegram service test is possible in this build environment; integration with an actual account and throughput must be independently tested on the user's VPS.
