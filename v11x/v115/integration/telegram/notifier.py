import argparse
import json
import sys
import logging
import mimetypes
import os
import shutil
import time
import urllib.parse
import urllib.request
import urllib.error
import uuid
import zipfile
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
PROJECT_ROOT = Path(os.getenv('TELEGRAM_PROJECT_ROOT', str(APP_DIR))).expanduser().resolve()
RUNTIME_DIR = PROJECT_ROOT / "runtime"
DEFAULT_QUEUE_DIR = RUNTIME_DIR / "telegram_queue"
DEFAULT_LOG_FILE = PROJECT_ROOT / "logs" / "telegram_worker.log"
DEFAULT_PID_FILE = RUNTIME_DIR / "telegram_worker.pid"
DEFAULT_STATUS_FILE = RUNTIME_DIR / "telegram_status.json"
DEFAULT_OFFSET_FILE = RUNTIME_DIR / "telegram_updates_offset.txt"

DEFAULT_REMOTE_BRIDGE_DIR = RUNTIME_DIR / "remote_bridge"


def resolve_remote_bridge_dir(remote_bridge_dir: Optional[str] = None) -> Path:
    return _resolve_path(remote_bridge_dir or os.getenv("TELEGRAM_REMOTE_BRIDGE_DIR"), DEFAULT_REMOTE_BRIDGE_DIR)


def ensure_remote_bridge_layout(remote_bridge_dir: Optional[str] = None) -> Path:
    base = resolve_remote_bridge_dir(remote_bridge_dir)
    for name in ("commands", "results", "state"):
        (base / name).mkdir(parents=True, exist_ok=True)
    return base


def infer_remote_bridge_dir_from_status(status_file: Optional[str] = None) -> Path:
    try:
        status_path = resolve_status_file(status_file)
        candidate = status_path.parent / "remote_bridge"
        for name in ("commands", "results", "state"):
            (candidate / name).mkdir(parents=True, exist_ok=True)
        return candidate.resolve()
    except Exception:
        return ensure_remote_bridge_layout()


def _resolve_path(raw: Optional[str], default: Path) -> Path:
    value = str(raw or "").strip()
    path = Path(value) if value else default
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.expanduser().resolve()


def resolve_queue_dir(queue_dir: Optional[str] = None) -> Path:
    return _resolve_path(queue_dir or os.getenv("TELEGRAM_QUEUE_DIR"), DEFAULT_QUEUE_DIR)


def resolve_log_file(log_file: Optional[str] = None) -> Path:
    return _resolve_path(log_file or os.getenv("TELEGRAM_WORKER_LOG"), DEFAULT_LOG_FILE)


def resolve_pid_file(pid_file: Optional[str] = None) -> Path:
    return _resolve_path(pid_file or os.getenv("TELEGRAM_WORKER_PID"), DEFAULT_PID_FILE)


def resolve_status_file(status_file: Optional[str] = None) -> Path:
    return _resolve_path(status_file or os.getenv("TELEGRAM_STATUS_FILE"), DEFAULT_STATUS_FILE)


def resolve_offset_file(offset_file: Optional[str] = None) -> Path:
    return _resolve_path(offset_file or os.getenv("TELEGRAM_OFFSET_FILE"), DEFAULT_OFFSET_FILE)


def ensure_queue_layout(queue_dir: Optional[str] = None) -> Path:
    base = resolve_queue_dir(queue_dir)
    for name in ("pending", "processing", "sent", "failed", "files"):
        (base / name).mkdir(parents=True, exist_ok=True)
    return base


class TelegramNotifier:
    def __init__(self, enabled: bool, bot_token: str, chat_id: str, queue_dir: Optional[str] = None):
        self.enabled = bool(enabled)
        self.bot_token = str(bot_token or "").strip()
        self.chat_id = str(chat_id or "").strip()
        self.queue_dir = ensure_queue_layout(queue_dir)

    def _assert_enabled(self) -> None:
        if not self.enabled:
            raise RuntimeError("Telegram notifier disabled")
        if not self.bot_token or not self.chat_id:
            raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")

    def _enqueue(self, payload: dict) -> Path:
        self._assert_enabled()
        item = dict(payload)
        item.setdefault("id", uuid.uuid4().hex)
        item.setdefault("created_ts", time.time())
        item["bot_token"] = self.bot_token
        item["chat_id"] = self.chat_id
        tmp_path = self.queue_dir / "pending" / f"{item['id']}.json.tmp"
        final_path = self.queue_dir / "pending" / f"{item['id']}.json"
        tmp_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(final_path)
        return final_path

    def send(self, text: str) -> Path:
        message = str(text or "").strip()
        if not message:
            raise RuntimeError("Telegram message is empty")
        return self._enqueue({"type": "message", "text": message})

    def send_photo(self, photo_path: str, caption: str = "") -> Path:
        src = Path(str(photo_path or "")).expanduser().resolve()
        if not src.exists() or not src.is_file():
            raise RuntimeError(f"Telegram photo not found: {src}")
        dest = self.queue_dir / "files" / f"{uuid.uuid4().hex}{src.suffix or '.bin'}"
        shutil.copy2(src, dest)
        return self._enqueue({"type": "photo", "photo_path": str(dest), "caption": str(caption or "")})


class TelegramQueueWorker:
    def __init__(self, bot_token: str, chat_id: str, queue_dir: Optional[str] = None, max_attempts: int = 10, status_file: Optional[str] = None, offset_file: Optional[str] = None, remote_bridge_dir: Optional[str] = None):
        self.bot_token = str(bot_token or "").strip()
        self.chat_id = str(chat_id or "").strip()
        self.queue_dir = ensure_queue_layout(queue_dir)
        self.max_attempts = max(1, int(max_attempts or 10))
        self.status_file = resolve_status_file(status_file)
        self.offset_file = resolve_offset_file(offset_file)
        self.remote_bridge_dir = ensure_remote_bridge_layout(remote_bridge_dir) if str(remote_bridge_dir or "").strip() else infer_remote_bridge_dir_from_status(status_file)
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        self.offset_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.bot_token or not self.chat_id:
            raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required for worker")

    def _pending_files(self):
        return sorted((self.queue_dir / "pending").glob("*.json"), key=lambda p: p.stat().st_mtime)

    def process_once(self) -> bool:
        for pending in self._pending_files():
            self._process_file(pending)
            return True
        return False

    def _api_get_json(self, method: str, params: dict | None = None) -> dict:
        query = urllib.parse.urlencode(params or {})
        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
        parsed = json.loads(body)
        if not parsed.get("ok"):
            raise RuntimeError(parsed.get("description") or f"Telegram {method} failed")
        return parsed

    def _download_telegram_file(self, file_id: str, dest_path: Path) -> Path:
        info = self._api_get_json("getFile", {"file_id": str(file_id or "").strip()})
        file_path = str((info.get("result") or {}).get("file_path") or "").strip()
        if not file_path:
            raise RuntimeError("Telegram getFile returned empty file_path")
        url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=120) as response:
            dest_path.write_bytes(response.read())
        return dest_path


    def _safe_extract_full_update_zip(self, archive_path: Path, payload_dir: Path) -> int:
        payload_dir.mkdir(parents=True, exist_ok=True)
        extracted = 0
        with zipfile.ZipFile(archive_path, 'r') as zf:
            members = [info for info in zf.infolist() if not info.is_dir()]
            rel_names = []
            for info in members:
                raw_name = str(info.filename or '').replace('\\', '/').strip('/ ')
                if not raw_name:
                    continue
                if raw_name.startswith('../') or '/..' in raw_name:
                    raise RuntimeError(f'invalid zip member path: {raw_name}')
                rel_names.append(raw_name)
            if not rel_names:
                raise RuntimeError('zip archive does not contain files')
            top_levels = {name.split('/', 1)[0] for name in rel_names if '/' in name}
            strip_prefix = ''
            if len(top_levels) == 1 and all(name.startswith(next(iter(top_levels)) + '/') for name in rel_names):
                strip_prefix = next(iter(top_levels)) + '/'
            for info in members:
                raw_name = str(info.filename or '').replace('\\', '/').strip('/ ')
                if not raw_name:
                    continue
                rel_name = raw_name[len(strip_prefix):] if strip_prefix and raw_name.startswith(strip_prefix) else raw_name
                rel_name = rel_name.strip('/ ')
                if not rel_name or rel_name == 'manifest.json':
                    continue
                if rel_name.startswith('../') or '/..' in rel_name:
                    raise RuntimeError(f'invalid extracted path: {rel_name}')
                dest = (payload_dir / rel_name).resolve()
                if not str(dest).startswith(str(payload_dir.resolve())):
                    raise RuntimeError(f'invalid extracted target: {rel_name}')
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, 'r') as src, open(dest, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                extracted += 1
        if extracted <= 0:
            raise RuntimeError('zip archive produced no payload files')
        return extracted

    def _clear_full_update_payload(self, payload_dir: Path) -> None:
        if not payload_dir.exists():
            return
        for child in sorted(payload_dir.iterdir()):
            try:
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
            except Exception:
                logging.exception("telegram full-update payload cleanup failed: %s", child)

    def _refresh_full_update_manifest(self, payload_dir: Path) -> Path:
        payload_dir.mkdir(parents=True, exist_ok=True)
        files = []
        for path in sorted(payload_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(payload_dir).as_posix()
            files.append({"source": rel, "target": rel})
        if not files:
            raise RuntimeError("no uploaded files found for full update")
        manifest = {
            "version": f"remote_upload_{time.strftime('%Y%m%d_%H%M%S')}",
            "description": "uploaded from telegram",
            "payload_dir": "payload",
            "restart_app": True,
            "files": files,
        }
        manifest_path = payload_dir.parent / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest_path

    def _handle_uploaded_document(self, msg: dict) -> bool:
        doc = msg.get("document") or {}
        file_id = str(doc.get("file_id") or "").strip()
        file_name = str(doc.get("file_name") or "uploaded.bin").strip() or "uploaded.bin"
        if not file_id:
            return False
        safe_name = Path(file_name).name
        updates_full = PROJECT_ROOT / "updates" / "full"
        payload_dir = updates_full / "payload"
        updates_full.mkdir(parents=True, exist_ok=True)
        self._clear_full_update_payload(payload_dir)
        manifest_file = updates_full / "manifest.json"
        try:
            manifest_file.unlink(missing_ok=True)
        except Exception:
            logging.exception("telegram full-update manifest cleanup failed: %s", manifest_file)
        if safe_name.lower().endswith('.zip'):
            archive_path = updates_full / safe_name
            try:
                archive_path.unlink(missing_ok=True)
            except Exception:
                pass
            self._download_telegram_file(file_id, archive_path)
            extracted_count = self._safe_extract_full_update_zip(archive_path, payload_dir)
            try:
                archive_path.unlink(missing_ok=True)
            except Exception:
                logging.exception("telegram full-update archive cleanup failed: %s", archive_path)
            manifest_path = self._refresh_full_update_manifest(payload_dir)
            self._send_message({"text": f"update file saved: {safe_name}\nmanifest: {manifest_path.name}\npayload files: {extracted_count}\nUse /update_full"})
            return True
        dest_path = payload_dir / safe_name
        self._download_telegram_file(file_id, dest_path)
        manifest_path = self._refresh_full_update_manifest(payload_dir)
        self._send_message({"text": f"update file saved: {safe_name}\nmanifest: {manifest_path.name}\npayload files: 1\nUse /update_full"})
        return True

    def _process_commands(self) -> bool:
        offset = 0
        try:
            raw = self.offset_file.read_text(encoding="utf-8").strip()
            if raw:
                offset = int(raw)
        except Exception:
            offset = 0
        params = {"timeout": 1, "allowed_updates": json.dumps(["message"])}
        if offset > 0:
            params["offset"] = offset + 1
        query = urllib.parse.urlencode(params)
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates?{query}"
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8", errors="replace")
        parsed = json.loads(body)
        if not parsed.get("ok"):
            raise RuntimeError(parsed.get("description") or "Telegram getUpdates failed")
        handled = False
        last_update_id = offset
        for item in parsed.get("result") or []:
            update_id = int(item.get("update_id") or 0)
            if update_id > last_update_id:
                last_update_id = update_id
            msg = item.get("message") or item.get("edited_message") or {}
            text = str(msg.get("text") or "").strip()
            chat = msg.get("chat") or {}
            chat_id = str(chat.get("id") or "").strip()
            if chat_id != self.chat_id:
                continue
            if text.startswith("/"):
                self._handle_command(text)
                handled = True
                continue
            if msg.get("document"):
                try:
                    doc_handled = self._handle_uploaded_document(msg)
                except Exception as exc:
                    logging.exception("telegram document upload failed: %s", exc)
                    self._send_message({"text": f"upload failed: {exc}"})
                    doc_handled = False
                handled = handled or doc_handled
                continue
        if last_update_id != offset:
            self.offset_file.write_text(str(last_update_id), encoding="utf-8")
        return handled

    def _remote_state_payload(self) -> dict:
        path = self.remote_bridge_dir / "state" / "remote_state.json"
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except Exception:
            return {}

    def _bridge_command(self, command: str, args: Optional[dict] = None, timeout_sec: int = 90) -> dict:
        command = str(command or "").strip().lower()
        command_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}_{command}"
        payload = {
            "command_id": command_id,
            "command": command,
            "args": dict(args or {}),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        cmd_path = self.remote_bridge_dir / "commands" / f"{command_id}.json"
        cmd_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        result_path = self.remote_bridge_dir / "results" / f"{command_id}.json"
        deadline = time.time() + max(5, int(timeout_sec or 90))
        while time.time() < deadline:
            if result_path.exists():
                return json.loads(result_path.read_text(encoding="utf-8"))
            time.sleep(0.25)
        raise RuntimeError(f"Remote command timeout: {command}")

    def _read_status_payload(self) -> dict:
        try:
            return json.loads(self.status_file.read_text(encoding="utf-8")) if self.status_file.exists() else {}
        except Exception:
            return {}

    def _build_status_text(self) -> str:
        payload = self._read_status_payload()
        remote = self._remote_state_payload()
        app_version = str((remote.get("app_version") if isinstance(remote, dict) else "") or payload.get("app_version") or "unknown")
        bot_running = bool(payload.get("bot_running", False))
        tg_worker = bool(payload.get("telegram_worker_running", False))
        timeframe = str(payload.get("timeframe") or "-")
        trade_mode = str(payload.get("trade_mode") or "-")
        open_positions = int(payload.get("open_positions") or 0)
        errors = int(payload.get("error_count") or 0)
        health = dict(payload.get("health") or {})
        connectivity_state = str(health.get("connectivity_state") or "IDLE")
        updated_at = str(payload.get("updated_at") or "-")
        return (
            f"OKX Turtle Bot {app_version}\n\n"
            f"bot: {'RUNNING' if (remote.get('bot_running') if isinstance(remote, dict) else bot_running) else 'STOPPED'}\n"
            f"telegram worker: {'ON' if tg_worker else 'OFF'}\n"
            f"timeframe: {timeframe}\n"
            f"mode: {trade_mode}\n"
            f"connectivity: {connectivity_state}\n"
            f"open positions: {open_positions}\n"
            f"errors: {errors}\n"
            f"updated: {updated_at}"
        )

    def _build_positions_text(self) -> str:
        payload = self._read_status_payload()
        positions = list(payload.get("positions") or [])
        if not positions:
            return "OPEN POSITIONS\nnone"
        lines = ["OPEN POSITIONS"]
        for idx, row in enumerate(positions[:12], start=1):
            inst = str(row.get("inst_id") or "-")
            side = str(row.get("side") or "-").upper()
            units = int(row.get("units") or 0)
            entry = float(row.get("entry") or 0.0)
            stop = float(row.get("stop") or 0.0)
            pnl = float(row.get("pnl") or 0.0)
            pnl_pct = float(row.get("pnl_pct") or 0.0)
            lines.append(f"{idx}. {inst} | {side} | units={units} | entry={entry:.6f} | stop={stop:.6f} | pnl={pnl:+.4f} ({pnl_pct:+.2f}%)")
        extra = max(0, len(positions) - 12)
        if extra > 0:
            lines.append(f"... ещё {extra}")
        return "\n".join(lines)

    def _build_balance_text(self) -> str:
        payload = self._read_status_payload()
        balance = dict(payload.get("balance") or {})
        return (
            "BALANCE\n"
            f"total: {float(balance.get('total') or 0.0):.2f} USDT\n"
            f"available: {float(balance.get('available') or 0.0):.2f} USDT\n"
            f"used: {float(balance.get('used') or 0.0):.2f} USDT\n"
            f"open positions: {int(payload.get('open_positions') or 0)}"
        )

    def _build_scanner_text(self) -> str:
        payload = self._read_status_payload()
        scanner = dict(payload.get("scanner") or {})
        top = list(payload.get("top_candidates") or [])
        lines = [
            "SCANNER",
            f"status: {scanner.get('status', 'IDLE')}",
            f"total: {int(scanner.get('total', 0) or 0)}",
            f"scanned: {int(scanner.get('scanned', 0) or 0)}",
            f"allowed: {int(scanner.get('allowed', 0) or 0)}",
            f"blocked: {int(scanner.get('blocked', 0) or 0)}",
            f"ready: {int(scanner.get('ready', 0) or 0)}",
            f"available after bans: {int(scanner.get('available_after_bans', 0) or 0)}/{int(scanner.get('scan_universe_total', 0) or 0)}",
        ]
        if top:
            lines.append("")
            lines.append("top candidate:")
            for item in top[:3]:
                lines.append(f"- {item.get('inst_id', '-')} | {str(item.get('side', '-')).upper()} | {item.get('system_name', 'Turtle')}")
        return "\n".join(lines)

    def _build_errors_text(self) -> str:
        payload = self._read_status_payload()
        rows = list(payload.get("latest_errors") or [])
        lines = [f"ERRORS\ntotal: {int(payload.get('error_count') or 0)}"]
        if not rows:
            lines.append("recent: none")
            return "\n".join(lines)
        lines.append("")
        lines.append("recent:")
        for idx, row in enumerate(rows[:5], start=1):
            title = str(row.get("title") or row.get("source") or "error")
            msg = str(row.get("message") or "").strip()
            if len(msg) > 120:
                msg = msg[:117] + "..."
            when = str(row.get("time") or "")
            lines.append(f"{idx}. {when} | {title}" + (f" | {msg}" if msg else ""))
        return "\n".join(lines)

    def _build_health_text(self) -> str:
        payload = self._read_status_payload()
        health = dict(payload.get("health") or {})
        components = dict(health.get("components") or {})
        lines = [
            "HEALTH",
            f"engine: {health.get('engine', 'STOPPED')}",
            f"telegram worker: {health.get('telegram_worker', 'OFF')}",
            f"connectivity: {health.get('connectivity_state', 'IDLE')}",
            f"market data errors: {int(health.get('market_data_errors', 0) or 0)}",
            f"cycle duration: {float(health.get('cycle_duration_sec', 0.0) or 0.0):.2f}s",
        ]
        if components:
            lines.append("")
            lines.append("components:")
            for name, state in components.items():
                lines.append(f"- {name}: {state}")
        return "\n".join(lines)

    def _handle_command(self, text: str) -> None:
        parts = str(text or "").strip().split()
        command = parts[0].split("@", 1)[0].lower() if parts else ""
        if command == "/ping":
            self._send_message({"text": "pong"})
        elif command == "/status":
            remote = self._remote_state_payload()
            if remote:
                base = self._build_status_text()
                extra = []
                if remote.get("busy"):
                    extra.append(f"remote busy: {remote.get('current_operation') or 'yes'}")
                if remote.get("last_result"):
                    extra.append(f"last: {remote.get('last_result')}")
                self._send_message({"text": base + ("\n" + "\n".join(extra) if extra else "")})
            else:
                self._send_message({"text": self._build_status_text()})
        elif command == "/start_bot":
            result = self._bridge_command("start_bot", timeout_sec=90)
            self._send_message({"text": str(result.get("message") or result.get("status") or "ok")})
        elif command == "/stop_bot":
            result = self._bridge_command("stop_bot", timeout_sec=90)
            self._send_message({"text": str(result.get("message") or result.get("status") or "ok")})
        elif command == "/reset_test":
            result = self._bridge_command("reset_test", timeout_sec=180)
            self._send_message({"text": str(result.get("message") or result.get("status") or "ok")})
        elif command == "/analysis":
            result = self._bridge_command("analysis", timeout_sec=900)
            file_path = Path(str(result.get("file_path") or "")).expanduser()
            if file_path.exists() and file_path.is_file():
                self._send_document(file_path, caption=str(result.get("message") or "analysis ready"))
            else:
                self._send_message({"text": str(result.get("message") or "analysis archive not found")})
        elif command == "/update_component":
            component = parts[1] if len(parts) > 1 else ""
            result = self._bridge_command("update_component", {"component": component}, timeout_sec=180)
            self._send_message({"text": str(result.get("message") or result.get("status") or "ok")})
        elif command == "/update_full":
            result = self._bridge_command("update_full", timeout_sec=300)
            self._send_message({"text": str(result.get("message") or result.get("status") or "ok")})
        elif command == "/positions":
            self._send_message({"text": self._build_positions_text()})
        elif command == "/balance":
            self._send_message({"text": self._build_balance_text()})
        elif command == "/scanner":
            self._send_message({"text": self._build_scanner_text()})
        elif command == "/errors":
            self._send_message({"text": self._build_errors_text()})
        elif command == "/health":
            self._send_message({"text": self._build_health_text()})
        elif command == "/chart":
            result = self._bridge_command("chart", timeout_sec=120)
            chart_path = Path(str(result.get("file_path") or "")).expanduser()
            if chart_path.exists() and chart_path.is_file():
                self._send_photo({"photo_path": str(chart_path), "caption": str(result.get("message") or "chart ready")})
            else:
                self._send_message({"text": str(result.get("message") or "Chart not ready yet. Окно должно быть открыто и не свернуто.")})
        elif command == "/help":
            self._send_message({"text": "Commands:\n/ping\n/status\n/positions\n/balance\n/scanner\n/errors\n/health\n/chart\n/analysis\n/start_bot\n/stop_bot\n/reset_test\n/update_component <name>\n/update_full\nSend a .py or other update file as a Telegram document, then run /update_full\n/help"})
        else:
            self._send_message({"text": "Unknown command. Use /help"})

    def _process_file(self, pending: Path) -> None:
        processing = self.queue_dir / "processing" / pending.name
        try:
            pending.replace(processing)
        except FileNotFoundError:
            return
        payload = json.loads(processing.read_text(encoding="utf-8"))
        payload["attempts"] = int(payload.get("attempts") or 0) + 1
        try:
            if payload.get("type") == "photo":
                self._send_photo(payload)
            else:
                self._send_message(payload)
            processing.replace(self.queue_dir / "sent" / processing.name)
        except Exception as exc:
            payload["last_error"] = str(exc)
            processing.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            target = self.queue_dir / ("failed" if payload["attempts"] >= self.max_attempts else "pending") / processing.name
            processing.replace(target)
            raise

    def _send_message(self, payload: dict) -> None:
        data = urllib.parse.urlencode({"chat_id": self.chat_id, "text": str(payload.get("text") or "")}).encode("utf-8")
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        request = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(request, timeout=25) as response:
            body = response.read().decode("utf-8", errors="replace")
        parsed = json.loads(body)
        if not parsed.get("ok"):
            raise RuntimeError(parsed.get("description") or "Telegram sendMessage failed")

    def _send_document(self, file_path: Path, caption: str = "") -> None:
        file_path = Path(file_path).resolve()
        if not file_path.exists():
            raise RuntimeError(f"Document file missing: {file_path}")
        boundary = f"----okxbot{uuid.uuid4().hex}"
        mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        parts: list[bytes] = []

        def add_field(name: str, value: str) -> None:
            parts.append(f"--{boundary}\r\n".encode("utf-8"))
            parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
            parts.append(value.encode("utf-8"))
            parts.append(b"\r\n")

        add_field("chat_id", self.chat_id)
        add_field("caption", str(caption or ""))
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(f'Content-Disposition: form-data; name="document"; filename="{file_path.name}"\r\n'.encode("utf-8"))
        parts.append(f"Content-Type: {mime}\r\n\r\n".encode("utf-8"))
        parts.append(file_path.read_bytes())
        parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(parts)
        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read().decode("utf-8", errors="replace")
        parsed = json.loads(raw)
        if not parsed.get("ok"):
            raise RuntimeError(parsed.get("description") or "Telegram sendDocument failed")

    def _send_photo(self, payload: dict) -> None:
        photo_path = Path(str(payload.get("photo_path") or "")).resolve()
        if not photo_path.exists():
            raise RuntimeError(f"Queued photo file missing: {photo_path}")
        boundary = f"----okxbot{uuid.uuid4().hex}"
        mime = mimetypes.guess_type(photo_path.name)[0] or "application/octet-stream"
        parts: list[bytes] = []

        def add_field(name: str, value: str) -> None:
            parts.append(f"--{boundary}\r\n".encode("utf-8"))
            parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
            parts.append(value.encode("utf-8"))
            parts.append(b"\r\n")

        add_field("chat_id", self.chat_id)
        add_field("caption", str(payload.get("caption") or ""))
        parts.append(f"--{boundary}\r\n".encode("utf-8"))
        parts.append(f'Content-Disposition: form-data; name="photo"; filename="{photo_path.name}"\r\n'.encode("utf-8"))
        parts.append(f"Content-Type: {mime}\r\n\r\n".encode("utf-8"))
        parts.append(photo_path.read_bytes())
        parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(parts)
        url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        with urllib.request.urlopen(request, timeout=40) as response:
            raw = response.read().decode("utf-8", errors="replace")
        parsed = json.loads(raw)
        if not parsed.get("ok"):
            raise RuntimeError(parsed.get("description") or "Telegram sendPhoto failed")


def run_worker_forever(queue_dir: Optional[str] = None, poll_interval: float = 2.0, max_attempts: int = 10, log_file: Optional[str] = None, pid_file: Optional[str] = None, status_file: Optional[str] = None, offset_file: Optional[str] = None, remote_bridge_dir: Optional[str] = None, stop_event=None) -> None:
    load_dotenv()
    queue_path = ensure_queue_layout(queue_dir)
    log_path = resolve_log_file(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(log_path), level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    pid_path = resolve_pid_file(pid_file)
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    bot_token = str(os.getenv("TELEGRAM_BOT_TOKEN", "")).strip()
    chat_id = str(os.getenv("TELEGRAM_CHAT_ID", "")).strip()
    worker = TelegramQueueWorker(bot_token=bot_token, chat_id=chat_id, queue_dir=str(queue_path), max_attempts=max_attempts, status_file=status_file, offset_file=offset_file, remote_bridge_dir=remote_bridge_dir)
    logging.info("Telegram worker started | app_dir=%s | project_root=%s | queue=%s | status=%s | bridge=%s", APP_DIR, PROJECT_ROOT, queue_path, resolve_status_file(status_file), ensure_remote_bridge_layout(remote_bridge_dir) if str(remote_bridge_dir or "").strip() else infer_remote_bridge_dir_from_status(status_file))
    try:
        idle_sleep = max(0.25, float(poll_interval or 2.0))
        while not (stop_event is not None and getattr(stop_event, "is_set", lambda: False)()):
            try:
                processed = worker.process_once()
                commands_processed = worker._process_commands()
                if not processed and not commands_processed:
                    if stop_event is not None and hasattr(stop_event, "wait"):
                        stop_event.wait(idle_sleep)
                    else:
                        time.sleep(idle_sleep)
            except Exception as exc:
                logging.exception("Telegram worker item processing failed: %s", exc)
                backoff = min(10.0, idle_sleep + 1.0)
                if stop_event is not None and hasattr(stop_event, "wait"):
                    stop_event.wait(backoff)
                else:
                    time.sleep(backoff)
    finally:
        try:
            pid_path.unlink(missing_ok=True)
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram queue worker for OKX Turtle Bot")
    parser.add_argument("--project-root", default=os.getenv("TELEGRAM_PROJECT_ROOT", str(PROJECT_ROOT)))
    parser.add_argument("--queue-dir", default=os.getenv("TELEGRAM_QUEUE_DIR", str(DEFAULT_QUEUE_DIR)))
    parser.add_argument("--poll-interval", type=float, default=float(os.getenv("TELEGRAM_WORKER_POLL_INTERVAL", "2.0")))
    parser.add_argument("--max-attempts", type=int, default=int(os.getenv("TELEGRAM_WORKER_MAX_ATTEMPTS", "10")))
    parser.add_argument("--log-file", default=os.getenv("TELEGRAM_WORKER_LOG", str(DEFAULT_LOG_FILE)))
    parser.add_argument("--pid-file", default=os.getenv("TELEGRAM_WORKER_PID", str(DEFAULT_PID_FILE)))
    parser.add_argument("--status-file", default=os.getenv("TELEGRAM_STATUS_FILE", str(DEFAULT_STATUS_FILE)))
    parser.add_argument("--offset-file", default=os.getenv("TELEGRAM_OFFSET_FILE", str(DEFAULT_OFFSET_FILE)))
    parser.add_argument("--remote-bridge-dir", default=os.getenv("TELEGRAM_REMOTE_BRIDGE_DIR", str(DEFAULT_REMOTE_BRIDGE_DIR)))
    args = parser.parse_args()
    os.environ['TELEGRAM_PROJECT_ROOT'] = str(Path(args.project_root).expanduser().resolve())
    globals()['PROJECT_ROOT'] = Path(os.environ['TELEGRAM_PROJECT_ROOT'])
    globals()['RUNTIME_DIR'] = globals()['PROJECT_ROOT'] / 'runtime'
    run_worker_forever(queue_dir=args.queue_dir, poll_interval=args.poll_interval, max_attempts=args.max_attempts, log_file=args.log_file, pid_file=args.pid_file, status_file=args.status_file, offset_file=args.offset_file, remote_bridge_dir=args.remote_bridge_dir)


if __name__ == "__main__":
    main()
