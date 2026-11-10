"""Verify opt-in 8-worker/16-transmission example configuration."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _calls(path: str) -> list[ast.Call]:
    tree = ast.parse((ROOT / path).read_text())
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)]


def _literal_kw(call: ast.Call, name: str):
    value = next(kw.value for kw in call.keywords if kw.arg == name)
    return ast.literal_eval(value)


def test_pyrogram_companion_uses_8_handler_workers_and_16_transmission_limit():
    constructors = [c for c in _calls('examples/integrate_pyrogram_companion.py')
                    if isinstance(c.func, ast.Name) and c.func.id == 'PyrogramClient']
    assert len(constructors) == 1
    assert _literal_kw(constructors[0], 'workers') == 8
    assert _literal_kw(constructors[0], 'max_concurrent_transmissions') == 16


def test_iqgram_companion_uses_8_download_and_8_upload_workers():
    options = [c for c in _calls('examples/integrate_pyrogram_companion.py')
               if isinstance(c.func, ast.Name) and c.func.id == 'TransferOptions']
    assert len(options) == 1
    assert _literal_kw(options[0], 'download_workers') == 8
    assert _literal_kw(options[0], 'upload_workers') == 8


def test_basic_iqgram_example_uses_requested_8_workers():
    options = [c for c in _calls('examples/basic.py')
               if isinstance(c.func, ast.Name) and c.func.id == 'TransferOptions']
    assert len(options) == 1
    assert _literal_kw(options[0], 'download_workers') == 8
    assert _literal_kw(options[0], 'upload_workers') == 8
