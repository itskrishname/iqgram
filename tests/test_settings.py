import pytest
from iqgram.settings import Settings


def test_config_parses_admin_ids_and_limits(tmp_path):
    settings = Settings(api_id=123, api_hash='a'*32, bot_token='123:abc', allowed_user_ids='123, 456', data_dir=tmp_path, max_concurrent_transmissions=8)
    assert settings.allowed_ids == frozenset({123, 456})
    assert settings.max_concurrent_transmissions == 8


def test_invalid_api_config_fails_before_network(tmp_path):
    with pytest.raises(ValueError, match='API_ID'):
        Settings(api_id=0, api_hash='a'*32, data_dir=tmp_path).validate('user')
    with pytest.raises(ValueError, match='BOT_TOKEN'):
        Settings(api_id=123, api_hash='a'*32, data_dir=tmp_path).validate('bot')


def test_download_path_never_escapes_base(tmp_path):
    from iqgram.paths import safe_upload_source
    root = tmp_path / 'downloads'
    root.mkdir()
    (root / 'video.mkv').write_bytes(b'abc')
    assert safe_upload_source(root, 'video.mkv').read_bytes() == b'abc'
    with pytest.raises(ValueError):
        safe_upload_source(root, '../private.txt')
