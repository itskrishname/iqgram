import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from iqgram.transfer import TransferEngine, TransferOptions, TransferError

CHUNK = 512 * 1024

class FakeBackend:
    def __init__(self, source: bytes=b''):
        self.source = source
        self.saved = {}
        self.download_ranges = []
        self.sent = None
        self.fail_part = None

    async def iter_range(self, media, offset, chunk_count, chunk_size):
        self.download_ranges.append((offset, chunk_count, chunk_size))
        for i in range(chunk_count):
            o = offset + i*chunk_size
            await asyncio.sleep(0)
            yield self.source[o:o+chunk_size]

    async def save_part(self, file_id, part, total_parts, data, is_big):
        await asyncio.sleep(0)
        if self.fail_part == part:
            raise RuntimeError('upstream failure')
        self.saved[part] = (data, is_big)
        return True

    async def send_uploaded(self, chat, handle, caption=None):
        self.sent = (chat, handle, caption)
        return {'id': 7}


def test_download_reassembles_out_of_order_parallel_ranges():
    source = bytes(range(256)) * (CHUNK*3//256) + b'last data'
    async def run():
        backend = FakeBackend(source)
        engine = TransferEngine(backend, TransferOptions(download_workers=3))
        with TemporaryDirectory() as d:
            output = Path(d)/'test.bin'
            result = await engine.download('media', len(source), output)
            assert output.read_bytes() == source
            assert result.bytes_transferred == len(source)
            assert len(backend.download_ranges) == 3
    asyncio.run(run())


def test_download_failure_does_not_leave_final_or_temp_file():
    async def run():
        backend = FakeBackend(b'A'*CHUNK)
        backend.source=b''
        engine = TransferEngine(backend)
        with TemporaryDirectory() as d:
            with pytest.raises(TransferError):
                await engine.download('media', CHUNK, Path(d)/'x.bin')
            assert list(Path(d).iterdir()) == []
    asyncio.run(run())


def test_upload_small_file_has_md5_and_sends_exact_parts():
    source=b'A'*(CHUNK+13)
    async def run():
        backend=FakeBackend()
        engine=TransferEngine(backend, TransferOptions(upload_workers=3))
        with TemporaryDirectory() as d:
            p=Path(d)/'a.bin';p.write_bytes(source)
            result=await engine.upload(p, 'me')
            assert result.bytes_transferred == len(source)
            assert b''.join(backend.saved[i][0] for i in sorted(backend.saved))==source
            assert backend.sent[0]=='me'
            assert backend.sent[1].big is False
            assert len(backend.sent[1].md5_checksum)==32
    asyncio.run(run())


def test_upload_failure_must_not_publish():
    async def run():
        backend=FakeBackend();backend.fail_part=1
        engine=TransferEngine(backend, TransferOptions(upload_workers=2))
        with TemporaryDirectory() as d:
            p=Path(d)/'a.bin';p.write_bytes(b'B'*(CHUNK+3))
            with pytest.raises(RuntimeError,match='upstream failure'):
                await engine.upload(p,'me')
            assert backend.sent is None
    asyncio.run(run())


def test_options_reject_invalid_concurrency():
    with pytest.raises(ValueError):
        TransferOptions(download_workers=0)
    with pytest.raises(ValueError):
        TransferOptions(upload_workers=200)


def test_download_refuses_overwrite():
    async def run():
        with TemporaryDirectory() as d:
            p=Path(d)/'a';p.write_bytes(b'existing')
            with pytest.raises(FileExistsError):
                await TransferEngine(FakeBackend(b'A'*10)).download('media',10,p)
            assert p.read_bytes()==b'existing'
    asyncio.run(run())


def test_megabyte_download_requests_preserve_final_partial_chunk():
    """Changing RPC request size must not corrupt or truncate the file."""
    mib = 1024 * 1024
    source = bytes(range(256)) * ((mib * 2) // 256) + b'end-of-file!'

    async def run():
        backend = FakeBackend(source)
        engine = TransferEngine(
            backend,
            TransferOptions(download_workers=4, upload_workers=4, download_request_size=mib),
        )
        with TemporaryDirectory() as td:
            out = Path(td) / 'megabyte.bin'
            result = await engine.download('x', len(source), out)
            assert out.read_bytes() == source
            assert result.bytes_transferred == len(source)
        assert backend.download_ranges
        assert all(chunk_size == mib for _, _, chunk_size in backend.download_ranges)
        assert sum(count for _, count, _ in backend.download_ranges) == 3
    asyncio.run(run())


def test_download_request_size_rejects_bad_values_and_keeps_default():
    assert TransferOptions().download_request_size == 512 * 1024
    for value in (0, 1024, 768 * 1024, 2 * 1024 * 1024, True):
        with pytest.raises(ValueError, match='download_request_size'):
            TransferOptions(download_request_size=value)


def test_megabyte_download_backend_error_cleans_up_partial_file():
    async def run():
        backend = FakeBackend(b'')
        engine = TransferEngine(backend, TransferOptions(download_request_size=1048576))
        with TemporaryDirectory() as td:
            with pytest.raises(TransferError):
                await engine.download('x', 1048576, Path(td) / 'out')
            assert list(Path(td).iterdir()) == []
    asyncio.run(run())
