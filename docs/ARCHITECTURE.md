# IQGram alpha architecture

```
Developer app (bot OR user)
  -> iqgram.Client (passes API ID, hash, optional bot token/session)
      -> TransferEngine (IQGram-owned scheduling)
          -> TelethonBackend (narrow adapter, subject to later replacement)
              -> Telethon MTProto auth, senders, datacenter routing, cryptography
                  -> Telegram servers
```

## Scheduling

A single `TransferEngine` instance has a configurable `asyncio.Semaphore` shared by its simultaneous downloads/uploads; default capacity is four, selected as `max(download_workers, upload_workers)`. Four is **not a hard cap**. Separate clients have independent budgets. Workers are logical scheduler lanes, not necessarily dedicated network connections.

Download divides aligned 512-KiB or 1-MiB ranges (selectable; 512 KiB default) across independent coroutine workers. Each worker opens one Telethon iter_download request iterator at a different offset; results are written by pwrite to the corresponding file offset with full-length validation. Final files are published only after every chunk succeeds, so a failed download cannot appear complete. The scheduled coroutines do not yet correspond 1:1 to dedicated MTProto TCP sessions.

Upload divides a file into 512-KiB parts, asynchronously dispatches saveFilePart (<=10 MiB) or saveBigFilePart (>10 MiB) to a bounded set of workers, and calls send_file with the resulting InputFile only after all parts are acknowledged. Small files get the required MD5 checksum. A retry of an entire upload may cause duplicate messages; the library does not run automatic upload retries.

## Important unfinished areas

- Telethon handles all MTProto auth and DC routing: IQGram is **not an independent protocol stack** yet.
- Client-session and message APIs currently cover core document media transfer, not every Pyrogram-compatible method.
- Dedicated media-only connection pools, full CDN verification custom logic, network-level cancellation, upload resume and adaptive tuning are planned, not implemented.
- The temporary download file occupies the full target size via ftruncate. Disk space must be sufficient.
- Avoid simultaneous processes sharing the same user session database.
- Check account-specific Telegram file size limits before transferring large files.
- No certified speed increase; benchmark against WZGram before asserting one.

## Security

No credentials are bundled. Application code supplies credentials to the constructor. Telethon session files contain authentication secrets; protect them and keep them out of Git. Never disable Telegram rate limit handling or request unauthorized content.
