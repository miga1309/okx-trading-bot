from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


class RemoteBridge:
    def _atomic_write_json(self, target: Path, payload: dict[str, Any], attempts: int = 6, delay_sec: float = 0.08) -> Path:
        last_error: Exception | None = None
        for idx in range(max(1, int(attempts or 1))):
            tmp = target.with_suffix(f".json.tmp.{idx}")
            try:
                tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                tmp.replace(target)
                return target
            except Exception as exc:
                last_error = exc
                try:
                    tmp.unlink(missing_ok=True)
                except Exception:
                    pass
                if idx + 1 < max(1, int(attempts or 1)):
                    time.sleep(max(0.01, float(delay_sec or 0.08)))
        if last_error is not None:
            raise last_error
        return target

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self.commands_dir = self.base_dir / "commands"
        self.results_dir = self.base_dir / "results"
        self.state_dir = self.base_dir / "state"
        for path in (self.commands_dir, self.results_dir, self.state_dir):
            path.mkdir(parents=True, exist_ok=True)

    def write_state(self, payload: dict[str, Any]) -> Path:
        target = self.state_dir / "remote_state.json"
        return self._atomic_write_json(target, payload)

    def list_pending_commands(self) -> list[Path]:
        return sorted(self.commands_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)

    def move_to_processing(self, path: Path) -> Path | None:
        processing = self.commands_dir / f"{path.stem}.processing"
        try:
            path.replace(processing)
        except FileNotFoundError:
            return None
        return processing

    def write_result(self, command_id: str, payload: dict[str, Any]) -> Path:
        target = self.results_dir / f"{command_id}.json"
        data = dict(payload or {})
        data.setdefault("command_id", command_id)
        data.setdefault("finished_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
        return self._atomic_write_json(target, data)

    @staticmethod
    def make_command_payload(command: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        command_id = f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{str(command or '').lower()}"
        return {
            "command_id": command_id,
            "command": str(command or "").strip().lower(),
            "args": dict(args or {}),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
