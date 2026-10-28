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


def worker_count(value: str) -> int:
    try:
        count = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('workers must be between 1 and 32') from exc
    if not 1 <= count <= 32:
        raise argparse.ArgumentTypeError('workers must be between 1 and 32')
    return count


def download_request_kib(value: str) -> int:
    try:
        size = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('download request size must be 512 or 1024 KiB') from exc
    if size not in (512, 1024):
        raise argparse.ArgumentTypeError('download request size must be 512 or 1024 KiB')
    return size


def show(event: Progress) -> None:
    print(f'\r{event.direction:8s} {event.percent:6.2f}% {event.bytes_per_second/1048576:8.2f} MiB/s', end='', flush=True)


async def main() -> None:
    parser = argparse.ArgumentParser(description='Benchmark IQGram media download/upload')
    parser.add_argument('--session', default='iqgram_benchmark')
    parser.add_argument('--chat', required=True, help='Chat username, ID, or me for user account')
    parser.add_argument('--message', type=int, required=True, help='Existing document message ID')
    parser.add_argument('--upload-chat', default=None, help='Optional destination for upload benchmark')
    parser.add_argument('--download-workers', type=worker_count, default=4, help='concurrent download workers (1-32; 4 default)')
    parser.add_argument('--upload-workers', type=worker_count, default=4, help='concurrent upload workers (1-32; 4 default)')
    parser.add_argument('--download-request-kib', type=download_request_kib, default=512,
                        help='download RPC request size in KiB (512 or 1024; 512 default)')
    args = parser.parse_args()

    api_id = env_int('IQGRAM_API_ID')
    api_hash = os.environ.get('IQGRAM_API_HASH', '')
    bot_token = os.environ.get('IQGRAM_BOT_TOKEN') or None
    if api_id <= 0 or not api_hash:
        raise SystemExit('Set IQGRAM_API_ID and IQGRAM_API_HASH environment variables first')

    opts = TransferOptions(
        download_workers=args.download_workers,
        upload_workers=args.upload_workers,
        download_request_size=args.download_request_kib * 1024,
    )
    print(f'IQGram benchmark: download_workers={opts.download_workers}, upload_workers={opts.upload_workers}, download_request_kib={args.download_request_kib}')
    async with Client(args.session, api_id, api_hash, bot_token=bot_token, options=opts) as iq:
        with tempfile.TemporaryDirectory(prefix='iqgram_bench_') as d:
            path = Path(d) / 'iqgram_test_media.bin'
            downloaded = await iq.download(args.chat, args.message, path, progress=show)
            print(f'\nDownload: {downloaded.bytes_per_second / 1048576:.2f} MiB/s ({downloaded.elapsed_seconds:.2f} seconds)')
            if args.upload_chat:
                uploaded = await iq.upload(path, args.upload_chat, progress=show)
                print(f'\nUpload: {uploaded.bytes_per_second / 1048576:.2f} MiB/s ({uploaded.elapsed_seconds:.2f} seconds)')
                print('Sent message ID:', getattr(uploaded.value, 'id', '<unknown>'))


if __name__ == '__main__':
    asyncio.run(main())
