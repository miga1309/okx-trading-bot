import logging
import mimetypes
import os
import threading
import urllib.parse
import urllib.request
from typing import Optional


class TelegramNotifier:
    def __init__(self, enabled: bool, bot_token: str, chat_id: str):
        self.enabled = bool(enabled and bot_token and chat_id)
        self.bot_token = str(bot_token or "").strip()
        self.chat_id = str(chat_id or "").strip()
        self._lock = threading.Lock()

    def _post_form(self, method: str, payload: dict) -> None:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        req = urllib.request.Request(url, data=data, method="POST")
        with self._lock:
            with urllib.request.urlopen(req, timeout=20) as resp:
                resp.read()

    def _post_multipart(self, method: str, fields: dict, file_field: str, file_path: str) -> None:
        boundary = f"----ChatGPTTelegramBoundary{threading.get_ident()}"
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
        body.extend(
            f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        body.extend(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
        body.extend(file_bytes)
        body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode("utf-8"))

        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        req = urllib.request.Request(
            url,
            data=bytes(body),
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with self._lock:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()

    def send(self, text: str) -> None:
        if not self.enabled:
            return
        text = str(text or "").strip()
        if not text:
            return
        try:
            self._post_form("sendMessage", {"chat_id": self.chat_id, "text": text})
        except Exception as exc:
            logging.warning("Telegram send failed: %s", exc)

    def send_photo(self, file_path: str, caption: Optional[str] = None) -> None:
        if not self.enabled:
            return
        file_path = str(file_path or "").strip()
        if not file_path:
            return
        if not os.path.exists(file_path):
            logging.warning("Telegram photo send failed: file does not exist: %s", file_path)
            return
        try:
            fields = {"chat_id": self.chat_id}
            caption_text = str(caption or "").strip()
            if caption_text:
                fields["caption"] = caption_text[:1024]
            self._post_multipart("sendPhoto", fields, "photo", file_path)
        except Exception as exc:
            logging.warning("Telegram photo send failed: %s", exc)
