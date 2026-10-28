# IQGram performance evaluation protocol

**Baseline supplied:** 2 MB/s upload and 2 MB/s download over a 1 Gbps advertised VPS link.

| Improvement goal | Speed target (MB/s) | Status |
| --- | ---: | --- |
| 1x baseline | 2 | User-reported, not independently measured |
| 5x | 10 | Proposed milestone, not measured |
| 10x | 20 | Proposed milestone, not measured |
| 25x | 50 | Experimental stretch, not measured |
| 50x | 100 | Aspirational, unverified; requires roughly 800 Mbps actual payload throughput |

## VPS measurements supplied by the project owner (2026-10-28)

File: 1415.32 MiB. IQGram v0.2.0 with Telethon 1.45, same VPS and user account; one run per setting. Reported values are observations, **not** statistically robust cross-library comparisons.

| Workers | Download (MiB/s) | Upload (MiB/s) |
| ---: | ---: | ---: |
| 1 | 5.79 | 5.53 |
| 4 | **16.76** | **17.52** |
| 8 | 15.81 | 16.79 |

v0.3.1 keeps **four workers as the default and target**, but removes v0.3.0's hard cap. A Client's shared concurrency budget defaults to four, derived from its configured worker counts. `--download-request-kib 1024` can now be compared with the known 512 KiB baseline without changing the number of workers. Those historical speeds belong to **v0.2.0**; **v0.3.1 has not been live-benchmarked**. Four workers were fastest among three single runs; repeat controlled tests and compare medians before concluding optimality.

Keep file size and media DC constant. Repeat WZGram and IQGram tests on the same VPS and account using identical source content. Report median wall time, MiB/s, CPU, RAM, disk I/O, sender RTT, TCP retransmissions and Telegram-specific errors. Conduct upload and download tests separately and account for which tests create a message. Never report aggregate speed of N files as single-file throughput.

IQGram's implementation is currently an alpha research candidate, not evidence of outperforming WZGram. In particular, the Telethon backend has no guaranteed dedicated connection pool per worker. The next genuine differentiation should be a native or dedicated MTProto media transport and automated adaptive benchmarking, not more app-level commands.

Telegram docs: https://core.telegram.org/api/files and https://core.telegram.org/api/optimisation
