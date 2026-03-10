import requests
import logging


class TelegramNotifier:
    def __init__(self, enabled: bool, bot_token: str = "", chat_id: str = ""):
        self.enabled = enabled
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, message: str):
        if not self.enabled:
            return

        if not self.bot_token or not self.chat_id:
            logging.warning("Telegram notifier: token or chat_id missing")
            return

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        payload = {
            "chat_id": self.chat_id,
            "text": message
        }

        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            logging.warning(f"Telegram send error: {e}")