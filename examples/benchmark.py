"""One-file IQGram benchmark: no config.py and no Telegram bot application.

Set IQGRAM_API_ID, IQGRAM_API_HASH and optionally IQGRAM_BOT_TOKEN in
local environment. Use a media message the account is authorized to read.
"""
import argparse
import asyncio
import os
import tempfile
from pathlib import Path

from iqgram import Client, Progress, TransferOptions


def env_int(name: str) -> int:
    value = os.environ.get(name, '0')
    try:
        return int(value)
    except ValueError:
        raise SystemExit(f'Invalid {name} (must be a numeric Telegram API ID)')


def show(event: Progress) -> None:
    print(f'\r{event.direction:8s} {event.percent:6.2f}% {event.bytes_per_second/1048576:8.2f} MiB/s', end='', flush=True)


async def main() -> None:
    parser = argparse.ArgumentParser(description='Benchmark IQGram media download/upload')
    parser.add_argument('--session', default='iqgram_benchmark')
    parser.add_argument('--chat', required=True, help='Chat username, ID, or me for user account')
    parser.add_argument('--message', type=int, required=True, help='Existing document message ID')
    parser.add_argument('--upload-chat', default=None, help='Optional destination for upload benchmark')
    parser.add_argument('--download-workers', type=int, default=4)
    parser.add_argument('--upload-workers', type=int, default=4)
    args = parser.parse_args()

    api_id = env_int('IQGRAM_API_ID')
    api_hash = os.environ.get('IQGRAM_API_HASH', '')
    bot_token = os.environ.get('IQGRAM_BOT_TOKEN') or None
    if api_id <= 0 or not api_hash:
        raise SystemExit('Set IQGRAM_API_ID and IQGRAM_API_HASH environment variables first')

    opts = TransferOptions(args.download_workers, args.upload_workers)
    async with Client(args.session, api_id, api_hash, bot_token=bot_token, options=opts) as iq:
        with tempfile.TemporaryDirectory(prefix='iqgram_bench_') as d:
            path = Path(d) / 'iqgram_test_media.bin'
            downloaded = await iq.download(args.chat, args.message, path, progress=show)
            print(f'\nDownload: {downloaded.bytes_per_second / 1048576:.2f} MiB/s')
            if args.upload_chat:
                uploaded = await iq.upload(path, args.upload_chat, progress=show)
                print(f'\nUpload: {uploaded.bytes_per_second / 1048576:.2f} MiB/s')
                print('Sent message ID:', getattr(uploaded.value, 'id', '<unknown>'))


if __name__ == '__main__':
    asyncio.run(main())
