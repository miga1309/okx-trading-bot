from __future__ import annotations

import csv
import json
import threading
from datetime import datetime
from pathlib import Path

class TradeLogger:
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        if not self.csv_path.exists():
            with self.csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "time",
                        "event",
                        "inst_id",
                        "side",
                        "qty",
                        "price",
                        "atr",
                        "stop_price",
                        "system_name",
                        "note",
                    ]
                )

    def log(self, event: str, inst_id: str, side: str, qty: float, price: float, atr: float, stop_price: float, system_name: str, note: str = "") -> None:
        with self.csv_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                event,
                inst_id,
                side,
                qty,
                price,
                atr,
                stop_price,
                system_name,
                note,
            ])

class EngineStatsLogger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(exist_ok=True)
        self.lock = threading.Lock()

    def log(self, event_type: str, **payload) -> None:
        event = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event": event_type,
        }
        event.update(self._normalize(payload))
        line = json.dumps(event, ensure_ascii=False)
        with self.lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def _normalize(self, value):
        if isinstance(value, dict):
            return {str(k): self._normalize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._normalize(v) for v in value]
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

class SignalAuditLogger(EngineStatsLogger):
    pass
