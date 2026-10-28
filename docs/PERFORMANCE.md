# IQGram performance evaluation protocol

**Baseline supplied:** 2 MB/s upload and 2 MB/s download over a 1 Gbps advertised VPS link.

| Improvement goal | Speed target (MB/s) | Status |
| --- | ---: | --- |
| 1x baseline | 2 | User-reported, not independently measured |
| 5x | 10 | Proposed milestone, not measured |
| 10x | 20 | Proposed milestone, not measured |
| 25x | 50 | Experimental stretch, not measured |
| 50x | 100 | Aspirational, unverified; requires roughly 800 Mbps actual payload throughput |

Keep file size and media DC constant. Repeat WZGram and IQGram tests on the same VPS and account using identical source content. Report median wall time, MiB/s, CPU, RAM, disk I/O, sender RTT, TCP retransmissions and Telegram-specific errors. Conduct upload and download tests separately and account for which tests create a message. Never report aggregate speed of N files as single-file throughput.

IQGram's implementation is currently an alpha research candidate, not evidence of outperforming WZGram. In particular, the Telethon backend has no guaranteed dedicated connection pool per worker. The next genuine differentiation should be a native or dedicated MTProto media transport and automated adaptive benchmarking, not more app-level commands.

Telegram docs: https://core.telegram.org/api/files and https://core.telegram.org/api/optimisation
