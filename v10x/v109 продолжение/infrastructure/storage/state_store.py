from __future__ import annotations

import json
from pathlib import Path


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self, default=None):
        if not self.path.exists():
            return default
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def save(self, payload) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
