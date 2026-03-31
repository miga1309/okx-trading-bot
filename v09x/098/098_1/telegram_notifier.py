import argparse
import json
import logging
import mimetypes
import os
import shutil
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = APP_DIR / "runtime"
DEFAULT_QUEUE_DIR = RUNTIME_DIR / "telegram_queue"
DEFAULT_LOG_FILE = APP_DIR / "logs" / "telegram_worker.log"
DEFAULT_PID_FILE = RUNTIME_DIR / "telegram_worker.pid"


def _resolve_path(raw: Optional[str], default: Path) -> Path:
    value = str(raw or "").strip()
    path = Path(value) if value else default
    if not path.is_absolute():
        path = APP_DIR / path
    return path.resolve()


def resolve_queue_dir(queue_dir: Optional[str] = None) -> Path:
    return _resolve_path(queue_dir or os.getenv("TELEGRAM_QUEUE_DIR"), DEFAULT_QUEUE_DIR)


def resolve_log_file(log_file: Optional[str] = None) -> Path:
    return _resolve_path(log_file or os.getenv("TELEGRAM_WORKER_LOG"), DEFAULT_LOG_FILE)


def resolve_pid_file(pid_file: Optional[str] = None) -> Path:
    return _resolve_path(pid_file or os.getenv("TELEGRAM_WORKER_PID"), DEFAULT_PID_FILE)


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
    def __init__(self, bot_token: str, chat_id: str, queue_dir: Optional[str] = None, max_attempts: int = 10):
        self.bot_token = str(bot_token or "").strip()
        self.chat_id = str(chat_id or "").strip()
        self.queue_dir = ensure_queue_layout(queue_dir)
        self.max_attempts = max(1, int(max_attempts or 10))
        if not self.bot_token or not self.chat_id:
            raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required for worker")

    def _pending_files(self):
        return sorted((self.queue_dir / "pending").glob("*.json"), key=lambda p: p.stat().st_mtime)

    def process_once(self) -> bool:
        for pending in self._pending_files():
            self._process_file(pending)
            return True
        return False

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


def run_worker_forever(queue_dir: Optional[str] = None, poll_interval: float = 2.0, max_attempts: int = 10, log_file: Optional[str] = None, pid_file: Optional[str] = None) -> None:
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
    worker = TelegramQueueWorker(bot_token=bot_token, chat_id=chat_id, queue_dir=str(queue_path), max_attempts=max_attempts)
    logging.info("Telegram worker started | queue=%s", queue_path)
    try:
        idle_sleep = max(0.25, float(poll_interval or 2.0))
        while True:
            try:
                processed = worker.process_once()
                if not processed:
                    time.sleep(idle_sleep)
            except Exception as exc:
                logging.exception("Telegram worker item processing failed: %s", exc)
                time.sleep(min(10.0, idle_sleep + 1.0))
    finally:
        try:
            pid_path.unlink(missing_ok=True)
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram queue worker for OKX Turtle Bot")
    parser.add_argument("--queue-dir", default=os.getenv("TELEGRAM_QUEUE_DIR", str(DEFAULT_QUEUE_DIR)))
    parser.add_argument("--poll-interval", type=float, default=float(os.getenv("TELEGRAM_WORKER_POLL_INTERVAL", "2.0")))
    parser.add_argument("--max-attempts", type=int, default=int(os.getenv("TELEGRAM_WORKER_MAX_ATTEMPTS", "10")))
    parser.add_argument("--log-file", default=os.getenv("TELEGRAM_WORKER_LOG", str(DEFAULT_LOG_FILE)))
    parser.add_argument("--pid-file", default=os.getenv("TELEGRAM_WORKER_PID", str(DEFAULT_PID_FILE)))
    args = parser.parse_args()
    run_worker_forever(queue_dir=args.queue_dir, poll_interval=args.poll_interval, max_attempts=args.max_attempts, log_file=args.log_file, pid_file=args.pid_file)


if __name__ == "__main__":
    main()
