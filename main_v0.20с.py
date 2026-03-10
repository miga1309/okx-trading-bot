import logging
from telegram_notifier import TelegramNotifier


APP_VERSION = "v0.20c"


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    logging.info(f"Starting OKX bot {APP_VERSION}")

    # настройки (позже вынесем в config.py)
    TELEGRAM_ENABLED = False
    TELEGRAM_TOKEN = ""
    TELEGRAM_CHAT_ID = ""

    telegram = TelegramNotifier(
        TELEGRAM_ENABLED,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    )

    telegram.send(f"Бот запущен {APP_VERSION}")

    # здесь будет запуск основного движка
    logging.info("Trading engine started")


if __name__ == "__main__":
    main()