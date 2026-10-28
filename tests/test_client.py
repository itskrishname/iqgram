from types import SimpleNamespace
import pytest
from iqgram.client import Client
from iqgram.settings import Settings


@pytest.mark.asyncio
async def test_bot_and_user_use_separate_underlying_sessions(tmp_path, monkeypatch):
    seen=[]
    class FakeRaw:
        def __init__(self, name, **kwargs):
            seen.append((name, kwargs))
        async def start(self):
            pass
        async def stop(self):
            pass
    monkeypatch.setitem(__import__('sys').modules, 'wzgram', SimpleNamespace(Client=FakeRaw))
    s=Settings(api_id=123,api_hash='a'*32,bot_token='123:abc',data_dir=tmp_path)
    async with Client('bot',s):
        pass
    async with Client('user',s):
        pass
    assert [p[0] for p in seen] == ['iqgram_bot','iqgram_user']
    assert seen[0][1]['bot_token'] == '123:abc'
    assert 'bot_token' not in seen[1][1]
    assert seen[0][1]['no_updates'] is True
    assert seen[1][1]['workdir'] == str(tmp_path/'sessions')


def test_invalid_credentials_fail_even_when_fake_transport_exists(tmp_path):
    with pytest.raises(ValueError,match='API_HASH'):
        Client('user',Settings(api_id=123,api_hash='short',data_dir=tmp_path),raw_client=object())
