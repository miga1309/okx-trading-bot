import logging
import threading
import urllib.parse
import urllib.request


class TelegramNotifier:
    def __init__(self, enabled: bool, bot_token: str, chat_id: str):
        self.enabled = bool(enabled and bot_token and chat_id)
        self.bot_token = str(bot_token or "").strip()
        self.chat_id = str(chat_id or "").strip()
        self._lock = threading.Lock()

    def send(self, text: str) -> None:
        if not self.enabled:
            return
        text = str(text or "").strip()
        if not text:
            return

        try:
            payload = urllib.parse.urlencode({
                "chat_id": self.chat_id,
                "text": text,
            }).encode("utf-8")

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            req = urllib.request.Request(url, data=payload, method="POST")

            with self._lock:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp.read()
        except Exception as exc:
            logging.warning("Telegram send failed: %s", exc)