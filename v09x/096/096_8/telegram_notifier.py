import argparse
import json
import logging
import mimetypes
import os
import shutil
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent


def _resolve_runtime_path(raw_value: Optional[str], default_relative: str) -> Path:
    raw = str(raw_value or "").strip()
    target = Path(raw) if raw else Path(default_relative)
    if not target.is_absolute():
        target = APP_DIR / target
    return target.resolve()


def _ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise NotADirectoryError(str(path))
    probe = path / f".__tg_probe__{uuid.uuid4().hex}.tmp"
    with open(probe, "w", encoding="utf-8") as f:
        f.write("ok")
    probe.unlink(missing_ok=True)
    return path


def _ensure_parent_directory(path: Path) -> Path:
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    if not parent.is_dir():
        raise NotADirectoryError(str(parent))
    probe = parent / f".__tg_parent_probe__{uuid.uuid4().hex}.tmp"
    with open(probe, "w", encoding="utf-8") as f:
        f.write("ok")
    probe.unlink(missing_ok=True)
    return path


class TelegramNotifier:
    def __init__(self, enabled: bool, bot_token: str, chat_id: str, queue_dir: Optional[str] = None):
        self.enabled = bool(enabled and bot_token and chat_id)
        self.bot_token = str(bot_token or "").strip()
        self.chat_id = str(chat_id or "").strip()
        base_dir = _ensure_directory(_resolve_runtime_path(queue_dir or os.getenv("TELEGRAM_QUEUE_DIR", "runtime/telegram_queue"), "runtime/telegram_queue"))
        self.queue_dir = base_dir
        self.pending_dir = base_dir / "pending"
        self.processing_dir = base_dir / "processing"
        self.sent_dir = base_dir / "sent"
        self.failed_dir = base_dir / "failed"
        self.attachments_dir = base_dir / "attachments"
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.processing_dir.mkdir(parents=True, exist_ok=True)
        self.sent_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)
        self.attachments_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _enqueue(self, payload: dict) -> None:
        if not self.enabled:
            return
        payload = dict(payload)
        payload.setdefault("id", f"tg_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}")
        payload.setdefault("created_ts", time.time())
        payload.setdefault("attempts", 0)
        tmp_fd, tmp_name = tempfile.mkstemp(prefix="tg_", suffix=".json", dir=str(self.pending_dir))
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            final_path = self.pending_dir / f"{payload['id']}.json"
            os.replace(tmp_name, final_path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except Exception:
                pass
            raise

    def _copy_attachment(self, file_path: str) -> str:
        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(file_path)
        suffix = src.suffix or ".bin"
        dst = self.attachments_dir / f"{uuid.uuid4().hex}{suffix}"
        shutil.copy2(src, dst)
        return str(dst)

    def send(self, text: str) -> None:
        if not self.enabled:
            return
        text = str(text or "").strip()
        if not text:
            return
        try:
            self._enqueue({"type": "message", "text": text})
        except Exception as exc:
            logging.warning("Telegram enqueue failed: %s", exc)

    def send_photo(self, file_path: str, caption: Optional[str] = None) -> None:
        if not self.enabled:
            return
        file_path = str(file_path or "").strip()
        if not file_path:
            return
        if not os.path.exists(file_path):
            logging.warning("Telegram photo enqueue failed: file does not exist: %s", file_path)
            return
        try:
            copied_path = self._copy_attachment(file_path)
            payload = {"type": "photo", "file_path": copied_path}
            caption_text = str(caption or "").strip()
            if caption_text:
                payload["caption"] = caption_text[:1024]
            self._enqueue(payload)
        except Exception as exc:
            logging.warning("Telegram photo enqueue failed: %s", exc)


class TelegramQueueWorker:
    def __init__(self, bot_token: str, chat_id: str, queue_dir: Optional[str] = None, poll_interval: float = 2.0, max_attempts: int = 10):
        self.bot_token = str(bot_token or "").strip()
        self.chat_id = str(chat_id or "").strip()
        self.queue_dir = _ensure_directory(_resolve_runtime_path(queue_dir or os.getenv("TELEGRAM_QUEUE_DIR", "runtime/telegram_queue"), "runtime/telegram_queue"))
        self.pending_dir = self.queue_dir / "pending"
        self.processing_dir = self.queue_dir / "processing"
        self.sent_dir = self.queue_dir / "sent"
        self.failed_dir = self.queue_dir / "failed"
        self.attachments_dir = self.queue_dir / "attachments"
        for p in [self.pending_dir, self.processing_dir, self.sent_dir, self.failed_dir, self.attachments_dir]:
            p.mkdir(parents=True, exist_ok=True)
        self.poll_interval = max(float(poll_interval or 2.0), 0.2)
        self.max_attempts = max(int(max_attempts or 10), 1)
        self._lock = threading.Lock()

    def _post_form(self, method: str, payload: dict) -> bytes:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        req = urllib.request.Request(url, data=data, method="POST", headers={"User-Agent": "OKX-Turtle-Bot-TelegramWorker/1.0"})
        with self._lock:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read()

    def _post_multipart(self, method: str, fields: dict, file_field: str, file_path: str) -> bytes:
        boundary = f"----TelegramBoundary{threading.get_ident()}"
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        filename = os.path.basename(file_path)
        body = bytearray()
        for key, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
            body.extend(str(value).encode("utf-8"))
            body.extend(b"\r\n")
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode("utf-8"))
        body.extend(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
        body.extend(file_bytes)
        body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode("utf-8"))
        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        req = urllib.request.Request(url, data=bytes(body), method="POST", headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": "OKX-Turtle-Bot-TelegramWorker/1.0"})
        with self._lock:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()

    def _next_pending_file(self) -> Optional[Path]:
        items = sorted(self.pending_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        return items[0] if items else None

    def _claim(self, path: Path) -> Path:
        dst = self.processing_dir / path.name
        os.replace(path, dst)
        return dst

    def _mark_sent(self, path: Path, payload: dict) -> None:
        payload["sent_ts"] = time.time()
        dst = self.sent_dir / path.name
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        if payload.get("type") == "photo":
            try:
                Path(str(payload.get("file_path") or "")).unlink(missing_ok=True)
            except Exception:
                pass

    def _mark_failed_or_retry(self, path: Path, payload: dict, error: str) -> None:
        payload["attempts"] = int(payload.get("attempts", 0) or 0) + 1
        payload["last_error"] = str(error or "")
        payload["last_error_ts"] = time.time()
        if int(payload["attempts"]) >= self.max_attempts:
            dst = self.failed_dir / path.name
            with open(dst, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            return
        backoff = min(300, 10 * int(payload["attempts"]))
        payload["next_retry_ts"] = time.time() + backoff
        dst = self.pending_dir / path.name
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass

    def process_once(self) -> bool:
        path = self._next_pending_file()
        if path is None:
            return False
        claimed = self._claim(path)
        with open(claimed, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if float(payload.get("next_retry_ts", 0.0) or 0.0) > time.time():
            self._mark_failed_or_retry(claimed, payload, payload.get("last_error", "retry_wait"))
            return True
        try:
            if payload.get("type") == "photo":
                fields = {"chat_id": self.chat_id}
                caption_text = str(payload.get("caption") or "").strip()
                if caption_text:
                    fields["caption"] = caption_text[:1024]
                body = self._post_multipart("sendPhoto", fields, "photo", str(payload.get("file_path") or ""))
            else:
                body = self._post_form("sendMessage", {"chat_id": self.chat_id, "text": str(payload.get("text") or "")})
            payload["telegram_response"] = body.decode("utf-8", errors="ignore")[:2000]
            self._mark_sent(claimed, payload)
            return True
        except Exception as exc:
            logging.warning("Telegram worker send failed: %s", exc)
            self._mark_failed_or_retry(claimed, payload, str(exc))
            return True

    def run_forever(self) -> None:
        if not (self.bot_token and self.chat_id):
            raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required for worker")
        while True:
            had_work = self.process_once()
            if not had_work:
                time.sleep(self.poll_interval)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Telegram queue worker for OKX Turtle Bot")
    parser.add_argument("--queue-dir", default=os.getenv("TELEGRAM_QUEUE_DIR", "runtime/telegram_queue"))
    parser.add_argument("--poll-interval", type=float, default=float(os.getenv("TELEGRAM_WORKER_POLL_INTERVAL", "2.0")))
    parser.add_argument("--max-attempts", type=int, default=int(os.getenv("TELEGRAM_WORKER_MAX_ATTEMPTS", "10")))
    parser.add_argument("--log-file", default=os.getenv("TELEGRAM_WORKER_LOG", "runtime/telegram_worker.log"))
    args = parser.parse_args()
    queue_dir = _ensure_directory(_resolve_runtime_path(args.queue_dir, "runtime/telegram_queue"))
    log_path = _ensure_parent_directory(_resolve_runtime_path(args.log_file, "runtime/telegram_worker.log"))
    logging.basicConfig(filename=str(log_path), level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    worker = TelegramQueueWorker(
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        queue_dir=str(queue_dir),
        poll_interval=args.poll_interval,
        max_attempts=args.max_attempts,
    )
    worker.run_forever()


if __name__ == "__main__":
    main()
