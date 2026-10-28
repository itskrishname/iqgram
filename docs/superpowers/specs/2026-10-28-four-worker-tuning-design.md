# IQGram four-worker tuning design

## Intent
Users should get the fastest feasible one-file MTProto throughput while choosing exactly four transfer workers. Four is the default setting and benchmark target, **not** a library-enforced upper bound. No performance multiplier is guaranteed.

## Approaches
1. **Only remove hard cap** — minimal risk but offers no information on bottlenecks.
2. **Remove hard cap + selectable download RPC size + targeted diagnostics** — selected. Preserves known 512 KiB behavior while allowing 1 MiB download requests without increasing worker count, and produces comparable benchmark records.
3. **Write a new native MTProto transport immediately** — long-term possibility, but needs transport correctness, dedicated media sessions, CDN handling, and repeatable benchmarks; not valid to assert speed gains now.

## Behavior
- Default download and upload worker counts remain 4. Manual worker values 1..32 are permitted for library compatibility and experiments, without a special hard-coded maximum of four. A given Client's shared transfer-slot capacity is the greater of its configured download and upload concurrency, with default 4.
- Upload chunk part size remains 512 KiB per Telegram protocol.
- Download requests are configurable at 512 KiB (default, preserved baseline) or 1024 KiB (experimental; Telegram-compliant). Download chunk counting, offsets and final partial request validation must remain correct. No implicit extra download workers, no unrelated user sessions, and no hidden fan-out.
- CLI benchmark `--download-request-kib` 512/1024; keep `--download-workers` and `--upload-workers` defaults at 4. Output sample configuration and throughput as before.
- Existing client API continues to work; no mandatory new config.py, bot app or stored secrets.
- Real 50x speed target of 100 MB/s from a 2 MB/s baseline is a stretch objective, not demonstrated; limit claims to measured data.

## Constraints
No new third-party dependencies. Use existing Telethon adapter, with explicit traceability that it is not independent native MTProto. Preserve download atomic no-clobber, cancellation cleanup, small-file MD5, exact range validation. Test with synthetic backend before user runs VPS transfer. Do not hardcode credentials.

## Non-goals
No Telegram policy circumvention, no artificial speed numbers, no completed independent native transport claim.
