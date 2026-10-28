# IQGram V1 architecture

## Scope and capabilities

- Python SDK façade (`iqgram/client.py`) with two isolated account identity names (`iqgram_bot`, `iqgram_user`) under `DATA_DIR/sessions`.
- External maintained MTProto session layer: `wzgram==3.1.1` (asynchronous Telegram API calls, media connection pool, native Rust cryptography provided by dependency).
- `iqgram/transfer.py` wraps media resolution, safe-path downloads, file uploads, progress callbacks, monotonic throughput measurement.
- `iqgram/queue.py` supplies SQLite WAL job persistence and bounded concurrent workers.
- `iqgram/bot.py` supplies allowlisted Telegram chat commands; each user's queue jobs are controlled by their Telegram user ID.
- `iqgram/cli.py` supplies repeatable direct transfers and benchmarks using either account type.

## Data flow

`Command -> validate auth -> sqlite queued job -> worker -> client.get_messages -> client.download_media -> optional client.send_document -> persist result -> reply status`

SQLite is local single-process storage. Jobs in `queued` survive a restart; jobs in `running` become `interrupted`, because automatically replaying sends can duplicate a Telegram message. Retry starts a new full transfer. Byte-level resume has NOT been implemented.

## Performance methodology

Baseline: compare same file, same VPS, same account and Telegram region across runs; measure total bytes / monotonic duration. Separate one-file throughput from aggregate queue throughput. Avoid many arbitrary sessions, bypassing flood limits or claiming a network capacity equals Telegram throughput. Optimize WZGram knobs only after profiling. No independent native IQGram MTProto transport exists in V1.

## Security

Secrets in ignored config.py/environment. Explicit Telegram user ID allowlist for chat commands. Session files in restricted directory. No arbitrary path accepted in `/upload`; job must be completed and belong to caller. All Telegram permissions still enforced server-side.

## Next engineering milestones

1. Execute live Telegram smoke tests on VPS with explicit test destination, compare both bot and user account logins.
2. Add structured per-stage performance telemetry and throughput benchmark logs.
3. Implement byte-level download resume with session-safe stream APIs and checksums.
4. Profile native crypto and RPC scheduling, only then consider custom Rust transport extensions.
5. Add cross-process idempotency, distributed queue and multi-host session coordination if needed.
