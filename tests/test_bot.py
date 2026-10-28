import pytest
from iqgram.bot import get_arg, allowed
from iqgram.settings import Settings


def test_bot_denies_unauthorized_and_empty_allowlist(tmp_path):
    s=Settings(api_id=123,api_hash='a'*32,bot_token='123:abc', data_dir=tmp_path,allowed_user_ids='12')
    assert allowed(12,s)
    assert not allowed(13,s)
    assert not allowed(None,s)


@pytest.mark.parametrize('invalid',['/cancel','/cancel 0','/cancel ../../etc','/cancel -2'])
def test_cancel_rejects_nonpositive_or_malformed_ids(invalid):
    with pytest.raises(ValueError,match='Usage:'):
        get_arg(invalid, 'cancel')
