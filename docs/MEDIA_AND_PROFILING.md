# Media support and throughput honesty (IQGram 0.5.0)

The underlying Telegram MTProto API distinguishes **bytes** from **message types**. For any extension, use `Client.upload(path, chat, media_kind='document')` and `Client.download(chat, message_id, path)`; known-size media uses the 4-worker default parallel download. Photo/document messages with unknown size use Telethon's single-stream fallback and atomic no-overwrite publication. Documents preserve bytes, but Telegram imposes file size/account quotas and message restrictions.

| media_kind | Relevant formats | Telegram representation | Caveat |
| --- | --- | --- | --- |
| document | arbitrary extension (.zip/.7z/.apk/.pdf/.mkv/.srt/...) | Generic document | Safe default; any content type treated as opaque bytes |
| auto | .jpg/.jpeg/.png; .mp4; common audio | Photo/video/audio heuristics | Unknown types become documents |
| photo | .jpg/.jpeg/.png | Native photo | Telegram may reject oversize / incompatible images; uploading pre-split bytes cannot resize |
| video | .mp4/.mov/.mkv/.webm/.avi etc | Video-intended document | Only supported MP4 generally streamable |
| audio | .mp3/.m4a/.ogg/.flac etc | Audio-intended document | Embedded metadata may be absent |
| voice | .ogg/.opus | Voice note | Must be Telegram-compatible Opus codec |
| video_note | .mp4 | Round video note | Dimensions and codecs must comply |
| animation | .gif/.mp4 | Animated media | May need Telegram-accepted encoding |
| sticker | .webp/.webm/.tgs | Sticker attribute | Valid sticker encoding/metadata is required |

`Client.raw` exposes Telethon for **other Telegram message constructors**: text, contacts, polls, dice, location, venue, game, story references, messages containing paid media, and more. These are *not* arbitrary downloadable files and are not covered by `Client.download/upload` as byte streams. Protected media and secret chats are not bypassed.

### Speed controls

- 4 logical transfer workers by default; default shared concurrency budget 4, no hard 4-worker limit
- 512 KiB upload parts, depth 1 by default; depth 2/4 experimental, can be slower
- 512 or 1024 KiB download request size; no verified speedup vs smaller requests
- `--profile-download` reports iterator wait and disk write per worker (includes scheduling overhead, not raw RTT)
- `--crypto cryptg` is default and `--crypto warpcrypto` is opt-in only after AES-IGE parity selftests; changes process-global Telethon AES methods
- For media already on Telegram, `reuse_media` avoids moving bytes through VPS (does not increase actual bandwidth)

### Data from user's VPS

1.38 GiB file, 4 workers: early 16.76 MiB/s download, 17.52 MiB/s upload; later 17.23 MiB/s download, 18.68 MiB/s upload best individual runs, but repeated download tests fell to ~9.42–9.53 MiB/s with ~6% process CPU. This does **not** prove a stable optimization or a CPU bottleneck. Telegram DC, transport wait, bandwidth routing and throttling still need controlled tests.

A 50x improvement over a claimed **2 MB/s** baseline is **100 MB/s** sustained. The VPS 1 Gbps link has theoretical maximum 125 MB/s before protocol overhead, so the objective is physically possible only under near-line-rate upstream/Telegram conditions; there is no guarantee. This release provides diagnostics and optional crypto validation, not proof of 50x performance.
