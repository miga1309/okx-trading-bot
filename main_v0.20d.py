import logging
from datetime import datetime
from typing import Optional

from config import APP_VERSION, get_default_config
from logger import setup_logging
from models import BotState, Snapshot
from telegram_notifier import TelegramNotifier


class Application:
    def __init__(self):
        self.config = get_default_config()
        self.state = BotState()
        self.telegram = TelegramNotifier(
            self.config.telegram.enabled,
            self.config.telegram.bot_token,
            self.config.telegram.chat_id
        )
        self.snapshot: Optional[Snapshot] = None

    def start(self) -> None:
        self.state.is_running = True
        self.state.last_update = datetime.now()
        self.state.last_engine_cycle = datetime.now()
        self.state.last_snapshot = datetime.now()

        logging.info(f"Starting OKX bot {APP_VERSION}")
        logging.info("Application initialized")
        logging.info("Trading engine started")

        self._notify_start()

    def stop(self) -> None:
        self.state.is_running = False
        self.state.last_update = datetime.now()

        logging.info("Trading engine stopped")
        logging.info("Application stopped")

        self._notify_stop()

    def run_cycle(self) -> None:
        """
        Один цикл работы приложения.
        Пока это заглушка-каркас для версии 0.20d.
        Сюда позже подключим:
        - получение данных рынка
        - обработку открытых позиций
        - сигналы стратегии
        - риск-менеджмент
        - обновление GUI
        """
        if not self.state.is_running:
            return

        now = datetime.now()
        self.state.last_update = now
        self.state.last_engine_cycle = now

        logging.info("Engine cycle executed")

        self.update_snapshot()

    def update_snapshot(self) -> None:
        """
        Обновление snapshot состояния.
        Пока формируется из текущего BotState.
        """
        now = datetime.now()
        self.snapshot = Snapshot(
            created_at=now,
            balance=0.0,
            used_margin=0.0,
            open_positions=len(self.state.open_positions),
            closed_trades=len(self.state.closed_trades),
            total_pnl_pct=0.0
        )
        self.state.last_snapshot = now

        logging.info(
            "Snapshot updated: open_positions=%s, closed_trades=%s",
            self.snapshot.open_positions,
            self.snapshot.closed_trades
        )

    def print_status(self) -> None:
        """
        Текстовый вывод текущего состояния.
        Полезно как временная замена GUI на этапе рефакторинга.
        """
        print("=" * 60)
        print(f"OKX TRADING BOT {APP_VERSION}")
        print("=" * 60)
        print(f"Running:            {self.state.is_running}")
        print(f"Last update:        {self.state.last_update_str()}")
        print(f"Last engine cycle:  {self.state.last_engine_cycle_str()}")
        print(f"Last snapshot:      {self.state.last_snapshot_str()}")
        print(f"Open positions:     {len(self.state.open_positions)}")
        print(f"Closed trades:      {len(self.state.closed_trades)}")

        if self.snapshot:
            print(f"Balance:            {self.snapshot.balance}")
            print(f"Used margin:        {self.snapshot.used_margin}")
            print(f"Total PnL %:        {self.snapshot.total_pnl_pct}")
        else:
            print("Snapshot:           not created yet")

        print("=" * 60)

    def _notify_start(self) -> None:
        try:
            self.telegram.send(f"Бот запущен {APP_VERSION}")
        except Exception as e:
            logging.warning(f"Failed to send start notification: {e}")

    def _notify_stop(self) -> None:
        try:
            self.telegram.send(f"Бот остановлен {APP_VERSION}")
        except Exception as e:
            logging.warning(f"Failed to send stop notification: {e}")


def main() -> None:
    setup_logging()

    app = Application()

    try:
        app.start()
        app.run_cycle()
        app.print_status()

    except KeyboardInterrupt:
        logging.info("Interrupted by user")

    except Exception as e:
        logging.exception(f"Unhandled error: {e}")

    finally:
        app.stop()


if __name__ == "__main__":
    main()