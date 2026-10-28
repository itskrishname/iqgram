# Security policy

- Set `API_ID`, `API_HASH`, `BOT_TOKEN` and `ALLOWED_USER_IDS` in untracked local `config.py` or environment variables; never commit live values.
- Revoke compromised bot tokens with @BotFather and rotate API credentials if exposed.
- Protect Telegram user login codes, session files and two-factor passwords. Sessions authorize your account and must never be shared.
- IQGram bot commands reject all users unless their numeric Telegram user ID is configured in `ALLOWED_USER_IDS`.
- Running user and bot sessions use separate session names, but only one process per session identity may own it at a time.
- `/upload` accepts only paths belonging to completed downloads owned by the requesting user; CLI upload deliberately accepts explicit local files for a trusted VPS operator.
- IQGram does not bypass protected chat/media permissions, flood waits, account restrictions or Telegram's server-side transfer limits.
- For production, run with non-root credentials and monitor resource usage, disk capacity and Telegram rate-limit errors.
