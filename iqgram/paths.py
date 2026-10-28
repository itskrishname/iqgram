"""Keep bot-requested local uploads inside an allowlisted downloads directory."""
from pathlib import Path


def safe_upload_source(base: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise ValueError('Supply a relative filename inside the downloads folder')
    root = Path(base).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Requested file is not an existing file under the downloads folder')
    return path
