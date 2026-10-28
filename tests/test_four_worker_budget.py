"""Four concurrent workers by default; no hard-coded maximum of four."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from iqgram import TransferEngine, TransferOptions

CHUNK = 512 * 1024


class MeasuredBackend:
    def __init__(self, source: bytes):
        self.source = source
        self.active = 0
        self.peak = 0
        self.saved = {}

    async def _enter(self):
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.015)

    def _leave(self):
        self.active -= 1

    async def iter_range(self, media, offset, chunk_count, chunk_size):
        await self._enter()
        try:
            for i in range(chunk_count):
                pos = offset + i * chunk_size
                yield self.source[pos:pos + chunk_size]
        finally:
            self._leave()

    async def save_part(self, file_id, part, total_parts, data, is_big):
        await self._enter()
        try:
            self.saved.setdefault(file_id, {})[part] = data
            return True
        finally:
            self._leave()

    async def send_uploaded(self, chat, handle, caption=None):
        return {"id": handle.file_id, "chat": chat}


def test_four_is_default_but_eight_is_allowed_for_explicit_configuration():
    assert TransferOptions().download_workers == 4
    assert TransferOptions().upload_workers == 4
    assert TransferOptions(download_workers=8, upload_workers=8).download_workers == 8
    assert TransferOptions(download_workers=1, upload_workers=1).upload_workers == 1


def test_eight_configured_workers_can_actually_run_in_parallel():
    async def run():
        source = b'Z' * (CHUNK * 8)
        backend = MeasuredBackend(source)
        engine = TransferEngine(backend, TransferOptions(download_workers=8, upload_workers=8))
        with TemporaryDirectory() as td:
            path = Path(td) / 'eight.bin'
            await engine.download('media', len(source), path)
            assert path.read_bytes() == source
        assert backend.peak == 8
        assert backend.active == 0
    asyncio.run(run())


def test_two_parallel_downloads_share_four_worker_budget():
    async def run():
        source = b'A' * (CHUNK * 4)
        backend = MeasuredBackend(source)
        engine = TransferEngine(backend, TransferOptions(download_workers=4))
        with TemporaryDirectory() as td:
            p1 = Path(td) / 'a.bin'
            p2 = Path(td) / 'b.bin'
            r1, r2 = await asyncio.gather(
                engine.download('a', len(source), p1),
                engine.download('b', len(source), p2)
            )
            assert (p1.read_bytes(), p2.read_bytes()) == (source, source)
            assert r1.bytes_transferred == r2.bytes_transferred == len(source)
        assert backend.peak == 4
        assert backend.active == 0
    asyncio.run(run())


def test_two_parallel_uploads_share_four_worker_budget():
    async def run():
        source = b'B' * (CHUNK * 4)
        backend = MeasuredBackend(source)
        engine = TransferEngine(backend, TransferOptions(upload_workers=4))
        with TemporaryDirectory() as td:
            path = Path(td) / 'upload.bin'
            path.write_bytes(source)
            a, b = await asyncio.gather(engine.upload(path, 'me'), engine.upload(path, 'me'))
            for result in (a, b):
                parts = backend.saved[result.value['id']]
                assert b''.join(parts[i] for i in sorted(parts)) == source
        assert backend.peak == 4
        assert backend.active == 0
    asyncio.run(run())


def test_download_and_upload_together_share_same_four_slots():
    async def run():
        source = b'C' * (CHUNK * 4)
        backend = MeasuredBackend(source)
        engine = TransferEngine(backend)
        with TemporaryDirectory() as td:
            a = Path(td) / 'input.bin'
            b = Path(td) / 'output.bin'
            a.write_bytes(source)
            got, sent = await asyncio.gather(
                engine.download('x', len(source), b), engine.upload(a, 'me')
            )
            assert b.read_bytes() == source
            assert sent.bytes_transferred == got.bytes_transferred == len(source)
        assert backend.peak <= 4
        assert backend.active == 0
    asyncio.run(run())


def test_cancelling_waiting_download_releases_slots_and_cleans_temp_file():
    class GatedBackend(MeasuredBackend):
        def __init__(self, source):
            super().__init__(source)
            self.ready = asyncio.Event()
            self.release = asyncio.Event()

        async def iter_range(self, media, offset, chunk_count, chunk_size):
            self.active += 1
            self.peak = max(self.peak, self.active)
            if self.active == 4:
                self.ready.set()
            try:
                if media == 'hold':
                    await self.release.wait()
                for i in range(chunk_count):
                    pos = offset + i * chunk_size
                    yield self.source[pos:pos + chunk_size]
            finally:
                self.active -= 1

    async def run():
        source = b'D' * (CHUNK * 4)
        backend = GatedBackend(source)
        engine = TransferEngine(backend)
        with TemporaryDirectory() as td:
            first = asyncio.create_task(engine.download('hold', len(source), Path(td) / 'hold'))
            await asyncio.wait_for(backend.ready.wait(), timeout=1)
            second = asyncio.create_task(engine.download('wait', len(source), Path(td) / 'wait'))
            await asyncio.sleep(0.02)
            second.cancel()
            with pytest.raises(asyncio.CancelledError):
                await second
            assert not list(Path(td).glob('wait*'))
            backend.release.set()
            await asyncio.wait_for(first, timeout=1)
            assert backend.active == 0
            result = await asyncio.wait_for(
                engine.download('after', len(source), Path(td) / 'after'), timeout=1
            )
            assert result.value.read_bytes() == source
            assert backend.peak <= 4
    asyncio.run(run())
