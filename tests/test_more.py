import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import pytest
from iqgram import TransferEngine, TransferOptions

CHUNK=512*1024

class Backend:
    def __init__(self,data=b''):
        self.data=data;self.saved={};self.handle=None
    async def iter_range(self, media, offset, chunk_count, chunk_size):
        for i in range(chunk_count):
            pos=offset+i*chunk_size
            await asyncio.sleep(0)
            yield self.data[pos:pos+chunk_size]
    async def save_part(self,file_id,part,total_parts,data,is_big):
        self.saved[part]=(data,is_big)
        return True
    async def send_uploaded(self,chat,handle,caption=None):
        self.handle=handle
        return 'ok'

def test_big_upload_uses_big_parts_and_no_checksum():
    async def run():
        backend=Backend()
        with TemporaryDirectory() as d:
            p=Path(d)/'big.bin';p.write_bytes(b'Z'*(10*1024*1024+17))
            result=await TransferEngine(backend,TransferOptions(upload_workers=4)).upload(p,'me')
            assert result.bytes_transferred==10*1024*1024+17
            assert backend.handle.big is True
            assert backend.handle.md5_checksum is None
            assert backend.handle.parts==21
            assert len(backend.saved)==21
            assert all(part[1] is True for part in backend.saved.values())
    asyncio.run(run())

def test_progress_async_callback_is_monotonic_and_finishes_at_100():
    async def run():
        source=b'X'*(CHUNK+15)
        backend=Backend(source)
        events=[]
        async def callback(event):
            events.append(event)
        with TemporaryDirectory() as d:
            result=await TransferEngine(backend).download('media',len(source),Path(d)/'out',progress=callback)
            assert result.bytes_transferred==len(source)
            assert events[-1].percent==100.0
            assert all(0 < e.percent <= 100 for e in events)
            assert [e.transferred for e in events]==sorted(e.transferred for e in events)
    asyncio.run(run())

def test_cancelled_download_cleans_up_partial_files():
    class SlowBackend(Backend):
        async def iter_range(self, media, offset, chunk_count, chunk_size):
            await asyncio.sleep(5)
            yield self.data[offset:offset+chunk_size]
    async def run():
        with TemporaryDirectory() as d:
            p=Path(d)/'x'
            task=asyncio.create_task(TransferEngine(SlowBackend(b'X'*CHUNK)).download('m', CHUNK, p))
            await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert not list(Path(d).iterdir())
    asyncio.run(run())
