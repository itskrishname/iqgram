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
from iqgram.media import MEDIA_KINDS


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


def pipeline_depth(value: str) -> int:
    try:
        depth = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('upload pipeline depth must be between 1 and 4') from exc
    if not 1 <= depth <= 4:
        raise argparse.ArgumentTypeError('upload pipeline depth must be between 1 and 4')
    return depth


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
    parser.add_argument('--upload-pipeline-depth', type=pipeline_depth, default=1,
                        help='experimental in-flight upload requests per worker (1-4; 1 default)')
    parser.add_argument('--crypto', choices=('cryptg', 'warpcrypto'), default='cryptg',
                        help='WarpCrypto is experimental, opt-in and process-wide; default cryptg')
    parser.add_argument('--profile-download', action='store_true',
                        help='print per-worker iterator wait, disk write and bytes (not raw TCP RTT)')
    parser.add_argument('--upload-kind', choices=sorted(MEDIA_KINDS), default='document',
                        help='native Telegram media mode for uploaded file (default: document)')
    args = parser.parse_args()

    api_id = env_int('IQGRAM_API_ID')
    api_hash = os.environ.get('IQGRAM_API_HASH', '')
    bot_token = os.environ.get('IQGRAM_BOT_TOKEN') or None
    if api_id <= 0 or not api_hash:
        raise SystemExit('Set IQGRAM_API_ID and IQGRAM_API_HASH environment variables first')

    if args.crypto == 'warpcrypto':
        from iqgram.crypto import enable_warpcrypto
        enable_warpcrypto()
        print('WarpCrypto AES-IGE parity checked; experimental backend active')

    opts = TransferOptions(
        download_workers=args.download_workers,
        upload_workers=args.upload_workers,
        download_request_size=args.download_request_kib * 1024,
        upload_pipeline_depth=args.upload_pipeline_depth,
    )
    print(f'IQGram benchmark: download_workers={opts.download_workers}, upload_workers={opts.upload_workers}, download_request_kib={args.download_request_kib}, upload_pipeline_depth={opts.upload_pipeline_depth}')
    async with Client(args.session, api_id, api_hash, bot_token=bot_token, options=opts) as iq:
        with tempfile.TemporaryDirectory(prefix='iqgram_bench_') as d:
            # Preserve message extension so native Telegram media modes work.
            message = await iq.raw.get_messages(args.chat, ids=args.message)
            original_name = getattr(getattr(message, 'file', None), 'name', None)
            clean_name = Path(str(original_name).replace('\\', '/')).name if original_name else 'iqgram_test_media.bin'
            if clean_name in ('', '.', '..'):
                clean_name = 'iqgram_test_media.bin'
            path = Path(d) / clean_name
            downloaded = await iq.download(args.chat, args.message, path, progress=show,
                                           profile=args.profile_download)
            print(f'\nDownload: {downloaded.bytes_per_second / 1048576:.2f} MiB/s ({downloaded.elapsed_seconds:.2f} seconds)')
            if downloaded.profile:
                print('Download profile (4 workers by default; times overlap):')
                for worker in downloaded.profile.workers:
                    print(f'  lane {worker.worker_index + 1}: {worker.chunks} chunks, '
                          f'{worker.transferred/1048576:.1f} MiB, '
                          f'iterator_wait={worker.read_wait_seconds:.2f}s, '
                          f'disk_write={worker.disk_write_seconds:.2f}s')
            if args.upload_chat:
                uploaded = await iq.upload(path, args.upload_chat, progress=show,
                                           media_kind=args.upload_kind)
                print(f'\nUpload: {uploaded.bytes_per_second / 1048576:.2f} MiB/s ({uploaded.elapsed_seconds:.2f} seconds)')
                print('Sent message ID:', getattr(uploaded.value, 'id', '<unknown>'))


if __name__ == '__main__':
    asyncio.run(main())
