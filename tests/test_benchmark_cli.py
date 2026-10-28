"""CLI contract: default four workers; no hard cap at four; 1MiB experiments."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / 'examples' / 'benchmark.py'


def command(*args: str):
    env = os.environ.copy()
    env.pop('IQGRAM_API_ID', None)
    env.pop('IQGRAM_API_HASH', None)
    return subprocess.run(
        [sys.executable, str(BENCH), '--chat', 'me', '--message', '7552', *args],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )


def test_benchmark_allows_eight_workers_even_without_credentials():
    run = command('--download-workers', '8', '--upload-workers', '4')
    assert run.returncode != 2
    assert 'Set IQGRAM_API_ID' in run.stderr


def test_benchmark_rejects_invalid_worker_count_before_credentials():
    run = command('--download-workers', '33')
    assert run.returncode == 2
    assert 'between 1 and 32' in run.stderr


def test_benchmark_can_select_one_megabyte_download_requests():
    run = command('--download-request-kib', '1024', '--download-workers', '4')
    assert run.returncode != 2
    assert 'Set IQGRAM_API_ID' in run.stderr


def test_benchmark_rejects_unaligned_download_requests():
    run = command('--download-request-kib', '768')
    assert run.returncode == 2
    assert '512 or 1024' in run.stderr


def test_benchmark_help_mentions_four_default_without_four_hard_cap():
    run = command('--help')
    assert run.returncode == 0
    assert '--download-request-kib' in run.stdout
    assert '4 default' in run.stdout
    assert '4 maximum' not in run.stdout
