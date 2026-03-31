from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def archive_directory(output_dir: Path, archive_name: str | None = None) -> Path:
    archive_name = archive_name or f'{output_dir.name}.zip'
    archive_path = output_dir / archive_name
    with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for p in output_dir.rglob('*'):
            if p == archive_path:
                continue
            if p.is_file():
                zf.write(p, arcname=p.relative_to(output_dir))
    return archive_path
