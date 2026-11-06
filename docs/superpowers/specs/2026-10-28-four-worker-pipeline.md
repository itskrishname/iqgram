# Four-worker pipelined upload experiment

## Intent
Improve IQGram's actual Telegram file-upload throughput with the user-preferred four upload workers, without pretending that a screenshot or a 1Gbps VPS proves any given performance number.

## Constraints
- Library only, bot and user login preserved, current Telethon adapter preserved.
- Default transfer worker count remains four, no hard four-worker cap.
- Default upload RPC pipeline depth stays one, for exact backward-compatible behavior; depth two or four is an explicit experimental opt-in and still uses four worker loops.
- 512 KiB upload parts, integer part indexing, Telegram's part ACK required before counting progress or sending media.
- Queue depth bounds memory; all outstanding requests cancelled on a part error; session state, user files and credentials are not packaged.
- Report true end-to-end wall-time throughput, not the sum of per-request instantaneous speeds.

## Approaches
- Increase workers: rejected; user insists benchmarking on four workers and 8 has been slower.
- Custom native MTProto transport: too risky to develop blindly and cannot live-test here.
- Bounded concurrent part RPCs *within* four worker loops (chosen): models Telegram's recommended local queue and lets us measure network pipelining safely.

## Validation
Synthetic tests prove bounded concurrency, file order/bytes and acknowledgement counts, cancellation, rejection/error cleanup, and CLI input validation. Live speed improvement is unknown until benchmarked on user's VPS.
