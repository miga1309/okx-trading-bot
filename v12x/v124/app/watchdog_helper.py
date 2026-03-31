from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except Exception:
        return False
    return True


def _read_last_heartbeat(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open('rb') as f:
            try:
                f.seek(-8192, os.SEEK_END)
            except OSError:
                f.seek(0)
            data = f.read().decode('utf-8', errors='ignore').splitlines()
        for line in reversed(data):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                return row
    except Exception:
        return {}
    return {}


def _write_event(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--version', type=str, default='')
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    logs = root / 'logs'
    heartbeat = logs / 'heartbeat.jsonl'
    out = logs / 'watchdog_events.jsonl'

    while True:
        if not _pid_alive(args.pid):
            last = _read_last_heartbeat(heartbeat)
            status = str(last.get('status') or '').lower()
            component = str(last.get('component') or '')
            abnormal = status not in {'shutdown', 'close_after_stop', 'thread_finished'}
            row = {
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'event': 'process_exit',
                'abnormal': bool(abnormal),
                'pid': int(args.pid),
                'version': str(args.version or ''),
                'last_component': component,
                'last_status': status,
                'last_heartbeat': last,
            }
            _write_event(out, row)
            return 0
        time.sleep(2.0)


if __name__ == '__main__':
    raise SystemExit(main())
