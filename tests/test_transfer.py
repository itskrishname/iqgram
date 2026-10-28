from pathlib import Path
from types import SimpleNamespace
import pytest
from iqgram.transfer import download_message, upload_file, format_rate


@pytest.mark.asyncio
async def test_download_rejects_non_media_before_transfer(tmp_path):
    class Client:
        async def get_messages(self,*args,**kwargs):
            return SimpleNamespace(document=None, video=None, photo=None, audio=None, voice=None, animation=None, sticker=None, video_note=None)
    with pytest.raises(ValueError, match='downloadable'):
        await download_message(Client(), 1, 3, tmp_path)


@pytest.mark.asyncio
async def test_download_uses_real_api_contract(tmp_path):
    class Client:
        async def get_messages(self,*args,**kwargs):
            assert kwargs == {'replies': 0}
            return SimpleNamespace(document=SimpleNamespace(file_size=4))
        async def download_media(self, message, file_name=None, progress=None):
            assert Path(file_name).is_dir()
            await progress(4,4)
            output = Path(file_name)/'file.bin'
            output.write_bytes(b'data')
            return str(output)
    progress_log=[]
    result=await download_message(Client(), 'me', 42, tmp_path, progress=lambda now,total: progress_log.append((now,total)))
    assert result.read_bytes() == b'data'
    assert progress_log == [(4,4)]


@pytest.mark.asyncio
async def test_upload_delivers_document(tmp_path):
    source=tmp_path/'file.txt'
    source.write_text('xyz')
    class Client:
        async def send_document(self, chat_id, document, caption=None, progress=None):
            assert (chat_id, document, caption) == ('me', str(source), 'test')
            await progress(3,3)
            return SimpleNamespace(id=55)
    got=[]
    result=await upload_file(Client(),'me',source,'test',lambda now,total:got.append(now))
    assert result.id == 55 and got == [3]


def test_rate_format_is_bytes_per_second():
    assert format_rate(2*1024*1024) == '2.00 MiB/s'
