# IQGram v0.5.0 — four-worker diagnostics and broad file media

**Goal:** Keep existing 4-worker default and backwards compatibility; support Telegram file media (document, photo, audio, voice, video, video note, GIF/animation and sticker) with explicit native media modes, unknown-size photo/document download fallback, transfer wait/IO diagnostics, and a safe WarpCrypto comparative microbenchmark (no untested global crypto monkeypatch).

**Constraints:** 50x is a target, never a verified release claim; no Telegram backend rate-limit bypass or extra workers as a performance trick. Preserve bot/user sessions and CLI args. No API secrets in deliverables.

**Design:** keep all byte transfer in TransferEngine, add UploadMedia spec to UploadedHandle, Telethon send_file flag resolver in new `media.py`. Known-size downloads remain parallel. Unknown-size photo/document downloads call Telethon's supported download_media to a temporary path with atomic no-overwrite publish. TransferResult has optional per-worker download profiling measuring iterator wait and disk write.

**Tests-first tasks:**
- [x] Native media send options, invalid kinds, existing document behavior
- [x] Client upload sets media kind and rejects invalid values early
- [x] Client unknown-size real photo/document fallback, no overwrite, other message types excluded
- [x] Download profile per worker, no-profile backwards compatibility
- [x] CLI prints profile data and selects upload kind
- [x] Local test suite, source zip, import/compile, verify filenames and no credentials

**Not supported:** Streaming calls, protected/paid media, secret chats, Telegram's non-file message types (poll/location/contact/game), guaranteed 100 MB/s, working WarpCrypto MTProto transport swap without verifying against live Telegram.
