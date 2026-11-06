"""Upload parts can pipeline within four workers without lying about progress."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from iqgram import TransferEngine, TransferOptions, TransferError

CHUNK = 512 * 1024


class ObservedBackend:
    def __init__(self, *, failed_part=None):
        self.active = 0
        self.peak = 0
        self.parts = {}
        self.failed_part = failed_part
        self.published = False

    async def save_part(self, file_id, part, total_parts, data, is_big):
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(0.025)
            if part == self.failed_part:
                raise ValueError('synthetic part failure')
            self.parts[part] = data
            return True
        finally:
            self.active -= 1

    async def send_uploaded(self, chat, handle, caption=None):
        self.published = True
        return {'id': 5}


@pytest.mark.parametrize(('depth', 'expected_peak'), [(1, 4), (2, 8), (4, 16)])
def test_pipeline_preserves_four_worker_loops_and_part_integrity(depth, expected_peak):
    async def run():
        backend = ObservedBackend()
        events = []
        engine = TransferEngine(backend, TransferOptions(upload_workers=4, upload_pipeline_depth=depth))
        source = bytes(range(256)) * (CHUNK * 16 // 256)
        with TemporaryDirectory() as td:
            path = Path(td) / 'input.bin'
            path.write_bytes(source)
            result = await engine.upload(path, 'me', progress=events.append)
        assert result.bytes_transferred == len(source)
        assert b''.join(backend.parts[i] for i in range(16)) == source
        assert backend.peak == expected_peak
        assert backend.active == 0
        assert backend.published is True
        assert events[-1].transferred == len(source)
        assert [event.transferred for event in events] == sorted(e.transferred for e in events)
    asyncio.run(run())


def test_pipeline_rejects_invalid_depth():
    for value in (0, 5, 33, -1, True, False, 2.0, '2'):
        with pytest.raises(ValueError, match='upload_pipeline_depth'):
            TransferOptions(upload_pipeline_depth=value)
    assert TransferOptions().upload_pipeline_depth == 1


def test_failed_pipelined_part_cancels_pending_and_never_publishes():
    async def run():
        backend = ObservedBackend(failed_part=3)
        engine = TransferEngine(backend, TransferOptions(upload_workers=4, upload_pipeline_depth=2))
        with TemporaryDirectory() as td:
            path = Path(td) / 'input.bin'
            path.write_bytes(b'Q' * CHUNK * 16)
            with pytest.raises(ValueError, match='synthetic part failure'):
                await engine.upload(path, 'me')
        assert backend.active == 0
        assert backend.published is False
    asyncio.run(run())


def test_rejected_ack_does_not_publish_pipelined_file():
    class RejectedBackend(ObservedBackend):
        async def save_part(self, file_id, part, total_parts, data, is_big):
            return False if part == 2 else await super().save_part(file_id, part, total_parts, data, is_big)

    async def run():
        backend = RejectedBackend()
        engine = TransferEngine(backend, TransferOptions(upload_workers=4, upload_pipeline_depth=2))
        with TemporaryDirectory() as td:
            path = Path(td) / 'input.bin'
            path.write_bytes(b'Z' * CHUNK * 10)
            with pytest.raises(TransferError, match='rejected'):
                await engine.upload(path, 'me')
        assert backend.active == 0
        assert not backend.published
    asyncio.run(run())


def test_cancel_pipelined_upload_drains_inflight_requests():
    class BlockedBackend(ObservedBackend):
        def __init__(self):
            super().__init__()
            self.ready = asyncio.Event()
            self.wait = asyncio.Event()

        async def save_part(self, file_id, part, total_parts, data, is_big):
            self.active += 1
            self.peak = max(self.peak, self.active)
            if self.active == 8:
                self.ready.set()
            try:
                await self.wait.wait()
                return True
            finally:
                self.active -= 1

    async def run():
        backend = BlockedBackend()
        engine = TransferEngine(backend, TransferOptions(upload_workers=4, upload_pipeline_depth=2))
        with TemporaryDirectory() as td:
            path = Path(td) / 'input.bin'
            path.write_bytes(b'X' * CHUNK * 16)
            task = asyncio.create_task(engine.upload(path, 'me'))
            await asyncio.wait_for(backend.ready.wait(), timeout=3)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=3)
            assert path.is_file()
        assert backend.active == 0
        assert backend.published is False
    asyncio.run(run())


def test_two_pipelined_uploads_share_four_logical_worker_slots():
    async def run():
        backend = ObservedBackend()
        engine = TransferEngine(backend, TransferOptions(upload_workers=4, upload_pipeline_depth=2))
        with TemporaryDirectory() as td:
            path = Path(td) / 'source.bin'
            path.write_bytes(b'F' * CHUNK * 16)
            first, second = await asyncio.gather(engine.upload(path, 'me'), engine.upload(path, 'me'))
        assert first.bytes_transferred == CHUNK * 16
        assert second.bytes_transferred == CHUNK * 16
        # One Client has at most 4 logical workers and each owns max 2 RPCs.
        assert 2 <= backend.peak <= 8
        assert backend.active == 0
    asyncio.run(run())
