from pathlib import Path
import shutil
import sys


SRC_NAME = "main_v021d_banlist_gui.py"
DST_NAME = "main_v022.py"


def log(msg: str) -> None:
    print(msg, flush=True)


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        fail(f"Не найден блок: {label}")
    return text.replace(old, new, 1)


def replace_between(text: str, start_marker: str, end_marker: str, new_block: str, label: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        fail(f"Не найден start_marker для {label}: {start_marker}")

    end = text.find(end_marker, start)
    if end == -1:
        fail(f"Не найден end_marker для {label}: {end_marker}")

    return text[:start] + new_block + text[end:]


def main() -> None:
    try:
        base = Path(__file__).resolve().parent
        src = base / SRC_NAME
        dst = base / DST_NAME
        backup = base / f"{DST_NAME}.bak"

        log("=== PATCH v022 START ===")

        if not src.exists():
            fail(f"Не найден исходный файл: {src}")

        text = src.read_text(encoding="utf-8")

        log("Шаг 1/12: APP_VERSION")
        text = replace_once(
            text,
            'APP_VERSION = "v021d-banlist"',
            'APP_VERSION = "v022"',
            "APP_VERSION",
        )

        log("Шаг 2/12: импорт QTableWidget")
        text = replace_once(
            text,
            "    QTabWidget,\n    QTableView,\n    QTextEdit,\n",
            "    QTabWidget,\n    QTableView,\n    QTableWidget,\n    QTableWidgetItem,\n    QTextEdit,\n",
            "QtWidgets import QTableWidget",
        )

        log("Шаг 3/12: BotConfig illiquid fields")
        text = replace_once(
            text,
            "    liquidity_min_24h_quote_volume: float = 2500000.0\n    illiquid_block_hours: int = 8\n",
            "    liquidity_min_24h_quote_volume: float = 2500000.0\n    illiquid_block_hours: int = 2\n    illiquid_soft_reject_cooldown_sec: int = 300\n    illiquid_repeats_for_ban: int = 3\n",
            "BotConfig illiquid fields",
        )

        log("Шаг 4/12: TurtleEngine illiquid_rejections")
        text = replace_once(
            text,
            "        self.close_retry_after: Dict[str, float] = {}\n        self.recent_stopouts: Dict[str, dict] = {}\n        self.illiquid_instruments: Dict[str, float] = {}\n        self.telegram = TelegramNotifier(\n",
            "        self.close_retry_after: Dict[str, float] = {}\n        self.recent_stopouts: Dict[str, dict] = {}\n        self.illiquid_instruments: Dict[str, float] = {}\n        self.illiquid_rejections: Dict[str, dict] = {}\n        self.telegram = TelegramNotifier(\n",
            "TurtleEngine illiquid_rejections init",
        )

        log("Шаг 5/12: _block_illiquid_instrument + _register_illiquid_rejection")
        new_illiquid_block = '''    def _block_illiquid_instrument(self, inst_id: str, reason: str) -> None:
        tf_sec = self._timeframe_seconds()

        if tf_sec <= 300:
            hours = 1
        elif tf_sec <= 900:
            hours = max(1, int(self.cfg.illiquid_block_hours))
        elif tf_sec <= 3600:
            hours = max(1, int(self.cfg.illiquid_block_hours) // 2 or 1)
        else:
            hours = 1

        until_ts = time.time() + hours * 3600
        self.illiquid_instruments[inst_id] = until_ts

        if inst_id not in self.temp_blocked_until or self.temp_blocked_until.get(inst_id, 0.0) < until_ts:
            self.temp_blocked_until[inst_id] = until_ts

        logging.info("%s: инструмент временно заблокирован как неликвидный на %sч (%s)", inst_id, hours, reason)

    def _register_illiquid_rejection(self, inst_id: str, reason: str) -> tuple[bool, str]:
        now_ts = time.time()
        data = self.illiquid_rejections.get(inst_id, {"count": 0, "last_reason": "", "last_ts": 0.0})

        gap_limit = max(60, int(self.cfg.illiquid_soft_reject_cooldown_sec))
        if now_ts - float(data.get("last_ts", 0.0)) > gap_limit * 3:
            data["count"] = 0

        data["count"] = int(data.get("count", 0)) + 1
        data["last_reason"] = reason
        data["last_ts"] = now_ts
        self.illiquid_rejections[inst_id] = data

        repeats_for_ban = max(2, int(self.cfg.illiquid_repeats_for_ban))
        tf_sec = self._timeframe_seconds()

        effective_repeats = repeats_for_ban
        if tf_sec >= 3600:
            effective_repeats += 1

        if data["count"] >= effective_repeats:
            return True, f"{reason}; повторов={data['count']}"

        soft_cd = max(60, int(self.cfg.illiquid_soft_reject_cooldown_sec))
        self.temp_blocked_until[inst_id] = max(self.temp_blocked_until.get(inst_id, 0.0), now_ts + soft_cd)
        return False, f"{reason}; мягкий пропуск {data['count']}/{effective_repeats}"

'''
        text = replace_between(
            text,
            "    def _block_illiquid_instrument(self, inst_id: str, reason: str) -> None:\n",
            "    def _check_liquidity(self, inst_id: str, price: float) -> tuple[bool, str]:\n",
            new_illiquid_block,
            "_block_illiquid_instrument section",
        )

        log("Шаг 6/12: evaluate_entry illiquid logic")
        text = replace_once(
            text,
            """        liquid_ok, liquid_reason = self._check_liquidity(inst_id, price)
        if not liquid_ok:
            self._block_illiquid_instrument(inst_id, liquid_reason)
            logging.info("%s: пропуск входа, illiquidity-filter (%s)", inst_id, liquid_reason)
            return
""",
            """        liquid_ok, liquid_reason = self._check_liquidity(inst_id, price)
        if not liquid_ok:
            should_ban, final_reason = self._register_illiquid_rejection(inst_id, liquid_reason)
            if should_ban:
                self._block_illiquid_instrument(inst_id, final_reason)
                logging.info("%s: пропуск входа, illiquidity-filter -> ban (%s)", inst_id, final_reason)
            else:
                logging.info("%s: пропуск входа, illiquidity-filter (%s)", inst_id, final_reason)
            return
""",
            "evaluate_entry illiquid logic",
        )

        log("Шаг 7/12: StartWindow theme init")
        text = replace_once(
            text,
            """    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"OKX Turtle Bot {APP_VERSION} — параметры запуска")
        self.setMinimumWidth(520)
        self._build_ui()
""",
            """    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"OKX Turtle Bot {APP_VERSION} — параметры запуска")
        self.setMinimumWidth(520)
        self._build_ui()
        self.apply_system_theme()
""",
            "StartWindow theme init",
        )

        log("Шаг 8/12: вкладка бан-листа -> таблица")
        text = replace_once(
            text,
            """        self.blocked_text = QTextEdit()
        self.blocked_text.setReadOnly(True)
        self.tabs.addTab(self.blocked_text, "Бан-лист")
""",
            """        self.blocked_table = QTableWidget()
        self.blocked_table.setColumnCount(4)
        self.blocked_table.setHorizontalHeaderLabels(["Инструмент", "Тип", "Причина", "Осталось"])
        self.blocked_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.blocked_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.blocked_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.blocked_table.setAlternatingRowColors(True)
        self.tabs.addTab(self.blocked_table, "Бан-лист")
""",
            "blocked tab widget",
        )

        log("Шаг 9/12: refresh_blocked_instruments_view")
        new_refresh = '''    def refresh_blocked_instruments_view(self) -> None:
        if not hasattr(self, "blocked_table"):
            return

        rows = self._collect_blocked_rows()

        if hasattr(self, "lbl_blocked_count"):
            self.lbl_blocked_count.setText(f"Блокировок: {len(rows)}")

        self.blocked_table.setRowCount(len(rows))

        for row_idx, (inst_id, block_type, reason, ttl) in enumerate(rows):
            values = [inst_id, block_type, reason, ttl]
            for col_idx, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                self.blocked_table.setItem(row_idx, col_idx, item)

        if not rows:
            self.blocked_table.setRowCount(1)
            self.blocked_table.setItem(0, 0, QTableWidgetItem("—"))
            self.blocked_table.setItem(0, 1, QTableWidgetItem("—"))
            self.blocked_table.setItem(0, 2, QTableWidgetItem("Активных блокировок нет"))
            self.blocked_table.setItem(0, 3, QTableWidgetItem("—"))

'''
        text = replace_between(
            text,
            "    def refresh_blocked_instruments_view(self) -> None:\n",
            "    def clear_ban_lists(self) -> None:\n",
            new_refresh,
            "refresh_blocked_instruments_view section",
        )

        log("Шаг 10/12: clear_ban_lists")
        new_clear = '''    def clear_ban_lists(self) -> None:
        if self.engine is None:
            if hasattr(self, "lbl_blocked_count"):
                self.lbl_blocked_count.setText("Блокировок: 0")
            if hasattr(self, "blocked_table"):
                self.blocked_table.setRowCount(1)
                self.blocked_table.setItem(0, 0, QTableWidgetItem("—"))
                self.blocked_table.setItem(0, 1, QTableWidgetItem("—"))
                self.blocked_table.setItem(0, 2, QTableWidgetItem("Бан-лист очищен."))
                self.blocked_table.setItem(0, 3, QTableWidgetItem("—"))
            self.append_log("Бан-лист очищен (движок ещё не запущен)")
            return

        for attr in ("blocked_instruments", "temp_blocked_until", "illiquid_instruments", "recent_stopouts", "illiquid_rejections"):
            data = getattr(self.engine, attr, None)
            if isinstance(data, dict):
                data.clear()

        self.refresh_blocked_instruments_view()
        self.append_log("Все заблокированные инструменты удалены из бан-листа")

'''
        text = replace_between(
            text,
            "    def clear_ban_lists(self) -> None:\n",
            "    def set_pending_config(self, cfg: BotConfig) -> None:\n",
            new_clear,
            "clear_ban_lists section",
        )

        log("Шаг 11/12: stop_engine cleanup")
        text = replace_once(
            text,
            """    def stop_engine(self) -> None:
        if self.engine:
            self.engine.stop()
            self.append_log("Остановка запрошена")
        if self.worker:
            self.worker.quit()
            self.worker.wait(2000)
        self._bot_running = False
        self._sync_toggle_button_state()
        self.refresh_blocked_instruments_view()
""",
            """    def stop_engine(self) -> None:
        if self.engine:
            self.engine.stop()
            self.append_log("Остановка запрошена")
        if self.worker:
            self.worker.quit()
            self.worker.wait(2000)
            self.worker = None
        self._bot_running = False
        self._sync_toggle_button_state()
        self.refresh_blocked_instruments_view()
""",
            "stop_engine cleanup",
        )

        log("Шаг 12/12: шаг графика в label")
        text = replace_once(
            text,
            """        self.balance_chart.update_points(balance_history, self.balance_chart_step_combo.currentData(), closed_markers)
        shown_points = len(self.balance_chart._bucket_points()) if hasattr(self.balance_chart, '_bucket_points') else 0
        self.lbl_balance_points.setText(f"Показано значений: {shown_points}/30")
""",
            """        self.balance_chart.update_points(balance_history, self.balance_chart_step_combo.currentData(), closed_markers)
        self.lbl_balance_step.setText(f"Шаг: {self.balance_chart_step_combo.currentData()}")
        shown_points = len(self.balance_chart._bucket_points()) if hasattr(self.balance_chart, '_bucket_points') else 0
        self.lbl_balance_points.setText(f"Показано значений: {shown_points}/30")
""",
            "on_snapshot chart step label",
        )

        text = replace_once(
            text,
            """        self.balance_chart.update_points(balance_history, self.balance_chart_step_combo.currentData(), closed_markers)
        self.lbl_balance_points.setText(f"Показано значений: {len(self.balance_chart._bucket_points())}/30")
""",
            """        self.balance_chart.update_points(balance_history, self.balance_chart_step_combo.currentData(), closed_markers)
        self.lbl_balance_step.setText(f"Шаг: {self.balance_chart_step_combo.currentData()}")
        self.lbl_balance_points.setText(f"Показано значений: {len(self.balance_chart._bucket_points())}/30")
""",
            "on_balance_chart_step_changed step label",
        )

        log("Проверка результата")
        must_have = [
            'APP_VERSION = "v022"',
            'illiquid_soft_reject_cooldown_sec: int = 300',
            'illiquid_repeats_for_ban: int = 3',
            'self.illiquid_rejections: Dict[str, dict] = {}',
            'def _register_illiquid_rejection(self, inst_id: str, reason: str) -> tuple[bool, str]:',
            'self.blocked_table = QTableWidget()',
            'QTableWidgetItem(str(value))',
            'self.worker = None',
            'self.lbl_balance_step.setText(f"Шаг: {self.balance_chart_step_combo.currentData()}")',
        ]
        for needle in must_have:
            if needle not in text:
                fail(f"Проверка не пройдена: {needle}")

        must_not_have = [
            'self.blocked_text = QTextEdit()',
        ]
        for needle in must_not_have:
            if needle in text:
                fail(f"В файле осталось лишнее: {needle}")

        if dst.exists():
            shutil.copy2(dst, backup)

        dst.write_text(text, encoding="utf-8")

        log("")
        log("ГОТОВО")
        log(f"Источник: {src.name}")
        log(f"Новая версия: {dst.name}")
        if backup.exists():
            log(f"Backup: {backup.name}")

    except Exception as e:
        print(f"\nОШИБКА: {e}", flush=True)
        raise


if __name__ == "__main__":
    main()