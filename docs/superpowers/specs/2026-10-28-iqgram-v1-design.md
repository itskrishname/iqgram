# IQGram V1 implementation scope

Intent: supply an installable, actually executable IQGram project for bot and user accounts with access to Telegram media upload/download, status and speed testing. The former deliverable was documentation-only and could not run.

Goals: direct CLI, allowlisted bot, isolated sessions, persistent queue, progress and repeatable speed measurements, two deployment choices. Deliverables must include tests, README, no secrets, real API calls through a maintained transport.

Approaches considered: (1) fully custom MTProto/Rust from scratch (not realistic to verify without long protocol integration); (2) maintain IQGram application layer and use WZGram MTProto transport (chosen); (3) copy an existing Pyrogram fork and rename it (high maintenance and unclear IP/license boundaries). The chosen approach maximizes usable features without inventing speed claims.

Constraints: no 50x guarantee, no fake transfer implementation, code runnable after installing dependencies and supplying Telegram credentials, explicit honest limitation on transport ownership and offline testing.
