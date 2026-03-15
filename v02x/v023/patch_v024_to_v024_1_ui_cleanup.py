# patch_v024_to_v024_1_ui_cleanup.py
# Создаёт новый файл main_v024_1.py на базе main_v024.py
#
# Изменения v024_1:
# - Добавлен changelog в начало файла
# - APP_VERSION: v024 -> v024_1
# - Удалена колонка "Средняя цена" из таблицы открытых позиций
# - "Добавлено юнитов" -> "Юнитов" в открытых и закрытых таблицах
# - Удалены поля статистики:
#   * Последнее обновление
#   * Последний цикл движка
#   * Последний snapshot
# - График баланса стал информативнее:
#   * добавлена шкала Y
#   * подписи уровней слева
#   * горизонтальные линии сетки с числами
#
# Использование:
#   python patch_v024_to_v024_1_ui_cleanup.py

from pathlib import Path
from datetime import datetime
import sys

SOURCE = Path("main_v024.py")
TARGET = Path("main_v024_1.py")


def fail(msg: str) -> None:
    print(f"ОШИБКА: {msg}")
    sys.exit(1)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        fail(f"Не найден блок: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if not SOURCE.exists():
        fail(f"Файл не найден: {SOURCE.resolve()}")

    text = SOURCE.read_text(encoding="utf-8")

    # ------------------------------------------------------------
    # 1) Версия
    # ------------------------------------------------------------
    text = replace_once(
        text,
        'APP_VERSION = "v024"',
        'APP_VERSION = "v024_1"',
        "app_version",
    )

    # ------------------------------------------------------------
    # 2) Changelog header
    # ------------------------------------------------------------
    changelog = f'''# ============================================================
# OKX Turtle Bot
# Version: v024_1
# Date: {datetime.now().strftime("%Y-%m-%d")}
# Based on: main_v024.py
#
# Changelog:
# - Removed "Средняя цена" column from open positions table
# - Renamed "Добавлено юнитов" to "Юнитов" in tables
# - Removed extra statistics fields from GUI
# - Improved balance chart with Y-axis labels and scale
# ============================================================

'''
    if not text.startswith("# ============================================================"):
        text = changelog + text

    # ------------------------------------------------------------
    # 3) Таблица открытых позиций: убрать "Средняя цена"
    # ------------------------------------------------------------
    old_headers_open = '''class PositionTableModel(QAbstractTableModel):
    HEADERS = [
        "Инструмент",
        "Сторона",
        "Qty",
        "Средняя цена",
        "Последняя цена",
        "PnL",
        "PnL %",
        "ATR",
        "ATR %",
        "Стоп",
        "До стопа %",
        "След. добор",
        "До добора %",
        "Сила тренда",
        "Добавлено юнитов",
        "Система",
        "Вход",
    ]
'''
    new_headers_open = '''class PositionTableModel(QAbstractTableModel):
    HEADERS = [
        "Инструмент",
        "Сторона",
        "Qty",
        "Последняя цена",
        "PnL",
        "PnL %",
        "ATR",
        "ATR %",
        "Стоп",
        "До стопа %",
        "След. добор",
        "До добора %",
        "Сила тренда",
        "Юнитов",
        "Система",
        "Вход",
    ]
'''
    text = replace_once(text, old_headers_open, new_headers_open, "position_headers")

    old_values_open = '''        values = [
            row.get("inst_id"),
            side_text,
            f"{row.get('qty', 0):.6f}",
            f"{row.get('avg_px', 0):.6f}",
            f"{row.get('last_px', 0):.6f}",
            f"{row.get('unrealized_pnl', 0):.4f}",
            f"{row.get('pnl_pct', 0):.2f}%",
            f"{row.get('atr', 0):.6f}",
            f"{row.get('atr_pct', 0):.2f}%",
            f"{row.get('stop_price', 0):.6f}",
            f"{row.get('stop_distance_pct', 0):.2f}%",
            f"{row.get('next_pyramid_price', 0):.6f}",
            f"{row.get('pyramid_distance_pct', 0):.2f}%",
            f"{row.get('trend_strength_atr', 0):.2f} ATR",
            str(int(row.get("added_units", max(0, int(row.get("units", 1)) - 1)))),
            row.get("system_name"),
            format_time_string(row.get("entry_time")),
        ]
'''
    new_values_open = '''        values = [
            row.get("inst_id"),
            side_text,
            f"{row.get('qty', 0):.6f}",
            f"{row.get('last_px', 0):.6f}",
            f"{row.get('unrealized_pnl', 0):.4f}",
            f"{row.get('pnl_pct', 0):.2f}%",
            f"{row.get('atr', 0):.6f}",
            f"{row.get('atr_pct', 0):.2f}%",
            f"{row.get('stop_price', 0):.6f}",
            f"{row.get('stop_distance_pct', 0):.2f}%",
            f"{row.get('next_pyramid_price', 0):.6f}",
            f"{row.get('pyramid_distance_pct', 0):.2f}%",
            f"{row.get('trend_strength_atr', 0):.2f} ATR",
            str(int(row.get("units", 1))),
            row.get("system_name"),
            format_time_string(row.get("entry_time")),
        ]
'''
    text = replace_once(text, old_values_open, new_values_open, "position_values")

    old_fg_open = '''        if role == Qt.ItemDataRole.ForegroundRole:
            if index.column() in (5, 6, 10, 12, 13):
                return gradient_pnl_color(pnl_pct if index.column() in (5, 6, 13) else -abs(float(row.get('stop_distance_pct' if index.column()==10 else 'pyramid_distance_pct', 0.0))))
            if index.column() == 1:
                return QColor(0, 120, 35) if row.get("side") == "long" else QColor(180, 30, 30)
            return QColor(20, 20, 20)
'''
    new_fg_open = '''        if role == Qt.ItemDataRole.ForegroundRole:
            if index.column() in (4, 5, 9, 11, 12):
                return gradient_pnl_color(
                    pnl_pct if index.column() in (4, 5, 12)
                    else -abs(float(row.get('stop_distance_pct' if index.column() == 9 else 'pyramid_distance_pct', 0.0)))
                )
            if index.column() == 1:
                return QColor(0, 120, 35) if row.get("side") == "long" else QColor(180, 30, 30)
            return QColor(20, 20, 20)
'''
    text = replace_once(text, old_fg_open, new_fg_open, "position_foreground")

    # ------------------------------------------------------------
    # 4) Таблица закрытых позиций: "Добавлено юнитов" -> "Юнитов"
    # ------------------------------------------------------------
    old_headers_closed = '''class ClosedTradesTableModel(QAbstractTableModel):
    HEADERS = [
        "Время",
        "Инструмент",
        "Сторона",
        "Qty",
        "Вход",
        "Выход",
        "PnL",
        "PnL %",
        "Длительность",
        "Добавлено юнитов",
        "Система",
        "Причина",
    ]
'''
    new_headers_closed = '''class ClosedTradesTableModel(QAbstractTableModel):
    HEADERS = [
        "Время",
        "Инструмент",
        "Сторона",
        "Qty",
        "Вход",
        "Выход",
        "PnL",
        "PnL %",
        "Длительность",
        "Юнитов",
        "Система",
        "Причина",
    ]
'''
    text = replace_once(text, old_headers_closed, new_headers_closed, "closed_headers")

    old_closed_values = '''            str(max(0, int(row.get("units", 1)) - 1)),
'''
    new_closed_values = '''            str(int(row.get("units", 1))),
'''
    text = replace_once(text, old_closed_values, new_closed_values, "closed_units_value")

    # ------------------------------------------------------------
    # 5) Удалить 3 поля из статистики
    # ------------------------------------------------------------
    old_metrics_labels = '''        self.lbl_status = QLabel("Статус: ожидание запуска")
        self.lbl_account = QLabel("Аккаунт: —")
        self.lbl_timeframe = QLabel("Таймфрейм: —")
        self.lbl_balance_summary = QLabel("Баланс: 0 | Использовано: 0 | Доступно: 0")
        self.lbl_positions = QLabel("Открытых позиций: 0")
        self.lbl_runtime = QLabel("Время работы: —")
        self.lbl_last_update = QLabel("Последнее обновление: —")
        self.lbl_engine_cycle = QLabel("Последний цикл движка: —")
        self.lbl_snapshot_signal = QLabel("Последний snapshot: —")
        self.lbl_cycle_duration = QLabel("Цикл движка: —")
        self.lbl_balance_trend = QLabel("Изменение баланса: Сегодня 0.00% | 7 дней 0.00%")
        self.lbl_risk_panel = QLabel("Использовано риска: 0.00% / 0.00%")
        self.lbl_trade_speed = QLabel("Сделок сегодня: 0 | Средняя длительность: —")
        labels = [
            self.lbl_status,
            self.lbl_account,
            self.lbl_timeframe,
            self.lbl_balance_summary,
            self.lbl_positions,
            self.lbl_runtime,
            self.lbl_last_update,
            self.lbl_engine_cycle,
            self.lbl_snapshot_signal,
            self.lbl_cycle_duration,
            self.lbl_balance_trend,
            self.lbl_risk_panel,
            self.lbl_trade_speed,
        ]
'''
    new_metrics_labels = '''        self.lbl_status = QLabel("Статус: ожидание запуска")
        self.lbl_account = QLabel("Аккаунт: —")
        self.lbl_timeframe = QLabel("Таймфрейм: —")
        self.lbl_balance_summary = QLabel("Баланс: 0 | Использовано: 0 | Доступно: 0")
        self.lbl_positions = QLabel("Открытых позиций: 0")
        self.lbl_runtime = QLabel("Время работы: —")
        self.lbl_cycle_duration = QLabel("Цикл движка: —")
        self.lbl_balance_trend = QLabel("Изменение баланса: Сегодня 0.00% | 7 дней 0.00%")
        self.lbl_risk_panel = QLabel("Использовано риска: 0.00% / 0.00%")
        self.lbl_trade_speed = QLabel("Сделок сегодня: 0 | Средняя длительность: —")
        labels = [
            self.lbl_status,
            self.lbl_account,
            self.lbl_timeframe,
            self.lbl_balance_summary,
            self.lbl_positions,
            self.lbl_runtime,
            self.lbl_cycle_duration,
            self.lbl_balance_trend,
            self.lbl_risk_panel,
            self.lbl_trade_speed,
        ]
'''
    text = replace_once(text, old_metrics_labels, new_metrics_labels, "metrics_labels_cleanup")

    old_on_snapshot_stats = '''        self.lbl_positions.setText(f"Открытых позиций: {len(payload['open_positions'])}")
        self.lbl_last_update.setText(f"Последнее обновление: {payload['timestamp']}")
        engine_info = payload.get("engine", {})
        self.lbl_engine_cycle.setText(f"Последний цикл движка: {engine_info.get('last_cycle_finished', '—')}")
        self.lbl_snapshot_signal.setText(f"Последний snapshot: {engine_info.get('last_snapshot_emitted', payload['timestamp'])}")
        cycle_duration = float(engine_info.get('last_cycle_duration_sec', 0.0) or 0.0)
'''
    new_on_snapshot_stats = '''        self.lbl_positions.setText(f"Открытых позиций: {len(payload['open_positions'])}")
        engine_info = payload.get("engine", {})
        cycle_duration = float(engine_info.get('last_cycle_duration_sec', 0.0) or 0.0)
'''
    text = replace_once(text, old_on_snapshot_stats, new_on_snapshot_stats, "on_snapshot_cleanup")

    # ------------------------------------------------------------
    # 6) Улучшить график: шкала Y
    # ------------------------------------------------------------
    old_paint_event = '''    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = self.rect()
        rect = outer.adjusted(12, 12, -12, -12)
        bg_color = QColor(15, 23, 42) if self.dark_theme else QColor(250, 250, 250)
        border_color = QColor(51, 65, 85) if self.dark_theme else QColor(210, 210, 210)
        muted_color = QColor(148, 163, 184) if self.dark_theme else QColor(120, 120, 120)
        grid_color = QColor(37, 48, 65) if self.dark_theme else QColor(232, 232, 232)
        text_color = QColor(226, 232, 240) if self.dark_theme else QColor(90, 90, 90)

        painter.fillRect(outer, bg_color)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(rect, 8, 8)

        bucketed = self._bucket_points()
        if not bucketed:
            painter.setPen(muted_color)
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "График баланса появится после накопления snapshot-истории")
            return

        plot = rect.adjusted(46, 22, -16, -34)
        values = [float(point.get("value", 0.0)) for point in bucketed]
        min_val = min(values)
        max_val = max(values)
        span = max_val - min_val
        pad = max(span * 0.15, max(abs(max_val), 1.0) * 0.01, 1.0)
        min_plot = min_val - pad
        max_plot = max_val + pad
        if abs(max_plot - min_plot) < 1e-12:
            max_plot += 1.0
            min_plot -= 1.0

        def value_to_y(value: float) -> int:
            return int(plot.bottom() - ((value - min_plot) / (max_plot - min_plot)) * plot.height())

        painter.setPen(QPen(grid_color, 1))
        for frac in (0.25, 0.5, 0.75):
            y = int(plot.top() + plot.height() * frac)
            painter.drawLine(plot.left(), y, plot.right(), y)

        if len(values) == 1:
            x_positions = [plot.center().x()]
        else:
            step_x = plot.width() / (len(values) - 1)
            x_positions = [plot.left() + i * step_x for i in range(len(values))]

        line_points = [(int(x), value_to_y(value)) for x, value in zip(x_positions, values)]
        start_value = values[0]
        end_value = values[-1]
        up_color = QColor(74, 222, 128) if self.dark_theme else QColor(60, 120, 60)
        down_color = QColor(248, 113, 113) if self.dark_theme else QColor(170, 60, 60)
        line_color = up_color if end_value >= start_value else down_color
        area_color = QColor(22, 101, 52, 110) if end_value >= start_value and self.dark_theme else (QColor(127, 29, 29, 110) if self.dark_theme else (QColor(208, 234, 214) if end_value >= start_value else QColor(246, 211, 211)))

        area = QPolygon()
        area.append(plot.bottomLeft())
        for x, y in line_points:
            area.append(QPoint(x, y))
        area.append(plot.bottomRight())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(area_color)
        painter.drawPolygon(area)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(line_color, 2))
        for i in range(1, len(line_points)):
            painter.drawLine(line_points[i - 1][0], line_points[i - 1][1], line_points[i][0], line_points[i][1])

        painter.setPen(Qt.PenStyle.NoPen)
        for idx, (x, y) in enumerate(line_points):
            painter.setBrush((QColor(203, 213, 225) if self.dark_theme else QColor(46, 46, 46)) if idx < len(line_points) - 1 else QColor(248, 168, 38))
            radius = 3 if idx < len(line_points) - 1 else 4
            painter.drawEllipse(x - radius, y - radius, radius * 2, radius * 2)

        marker_index = {str(point.get("time")): i for i, point in enumerate(bucketed)}
        for marker in self.markers[-200:]:
            idx = marker_index.get(str(marker.get("bucket_time")))
            if idx is None or idx >= len(line_points):
                continue
            x, y = line_points[idx]
            pnl = float(marker.get("pnl", 0.0))
            color = QColor(15, 135, 55) if pnl >= 0 else QColor(190, 45, 45)
            painter.setBrush(color)
            painter.drawEllipse(x - 2, y - 8, 4, 4)

        delta_value = end_value - start_value
        delta_pct = (delta_value / start_value * 100.0) if abs(start_value) > 1e-12 else 0.0
        painter.setPen(text_color)
        painter.drawText(rect.adjusted(6, 2, -6, -2), int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft), f"Max: {max_val:.2f}")
        painter.drawText(rect.adjusted(6, 2, -6, -2), int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft), f"Min: {min_val:.2f}")
        painter.drawText(rect.adjusted(6, 2, -6, -2), int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight), f"Шаг: {self.step_code} | Δ: {delta_value:+.2f} ({delta_pct:+.2f}%)")
        painter.drawText(rect.adjusted(6, 2, -6, -2), int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight), f"{bucketed[-1].get('time', '—')} | Последнее: {end_value:.2f} | Точек: {len(bucketed)}")
'''
    new_paint_event = '''    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = self.rect()
        rect = outer.adjusted(12, 12, -12, -12)
        bg_color = QColor(15, 23, 42) if self.dark_theme else QColor(250, 250, 250)
        border_color = QColor(51, 65, 85) if self.dark_theme else QColor(210, 210, 210)
        muted_color = QColor(148, 163, 184) if self.dark_theme else QColor(120, 120, 120)
        grid_color = QColor(37, 48, 65) if self.dark_theme else QColor(232, 232, 232)
        text_color = QColor(226, 232, 240) if self.dark_theme else QColor(90, 90, 90)

        painter.fillRect(outer, bg_color)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(rect, 8, 8)

        bucketed = self._bucket_points()
        if not bucketed:
            painter.setPen(muted_color)
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "График баланса появится после накопления snapshot-истории")
            return

        plot = rect.adjusted(70, 22, -16, -34)
        values = [float(point.get("value", 0.0)) for point in bucketed]
        min_val = min(values)
        max_val = max(values)
        span = max_val - min_val
        pad = max(span * 0.15, max(abs(max_val), 1.0) * 0.01, 1.0)
        min_plot = min_val - pad
        max_plot = max_val + pad
        if abs(max_plot - min_plot) < 1e-12:
            max_plot += 1.0
            min_plot -= 1.0

        def value_to_y(value: float) -> int:
            return int(plot.bottom() - ((value - min_plot) / (max_plot - min_plot)) * plot.height())

        painter.setPen(QPen(grid_color, 1))
        y_levels = []
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = int(plot.top() + plot.height() * frac)
            value = max_plot - (max_plot - min_plot) * frac
            y_levels.append((y, value))
            painter.drawLine(plot.left(), y, plot.right(), y)

        painter.setPen(text_color)
        for y, value in y_levels:
            painter.drawText(18, y + 5, f"{value:.2f}")

        if len(values) == 1:
            x_positions = [plot.center().x()]
        else:
            step_x = plot.width() / (len(values) - 1)
            x_positions = [plot.left() + i * step_x for i in range(len(values))]

        line_points = [(int(x), value_to_y(value)) for x, value in zip(x_positions, values)]
        start_value = values[0]
        end_value = values[-1]
        up_color = QColor(74, 222, 128) if self.dark_theme else QColor(60, 120, 60)
        down_color = QColor(248, 113, 113) if self.dark_theme else QColor(170, 60, 60)
        line_color = up_color if end_value >= start_value else down_color
        area_color = QColor(22, 101, 52, 110) if end_value >= start_value and self.dark_theme else (
            QColor(127, 29, 29, 110) if self.dark_theme else (
                QColor(208, 234, 214) if end_value >= start_value else QColor(246, 211, 211)
            )
        )

        area = QPolygon()
        area.append(plot.bottomLeft())
        for x, y in line_points:
            area.append(QPoint(x, y))
        area.append(plot.bottomRight())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(area_color)
        painter.drawPolygon(area)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(line_color, 2))
        for i in range(1, len(line_points)):
            painter.drawLine(line_points[i - 1][0], line_points[i - 1][1], line_points[i][0], line_points[i][1])

        painter.setPen(Qt.PenStyle.NoPen)
        for idx, (x, y) in enumerate(line_points):
            painter.setBrush(
                (QColor(203, 213, 225) if self.dark_theme else QColor(46, 46, 46))
                if idx < len(line_points) - 1 else QColor(248, 168, 38)
            )
            radius = 3 if idx < len(line_points) - 1 else 4
            painter.drawEllipse(x - radius, y - radius, radius * 2, radius * 2)

        marker_index = {str(point.get("time")): i for i, point in enumerate(bucketed)}
        for marker in self.markers[-200:]:
            idx = marker_index.get(str(marker.get("bucket_time")))
            if idx is None or idx >= len(line_points):
                continue
            x, y = line_points[idx]
            pnl = float(marker.get("pnl", 0.0))
            color = QColor(15, 135, 55) if pnl >= 0 else QColor(190, 45, 45)
            painter.setBrush(color)
            painter.drawEllipse(x - 2, y - 8, 4, 4)

        delta_value = end_value - start_value
        delta_pct = (delta_value / start_value * 100.0) if abs(start_value) > 1e-12 else 0.0
        painter.setPen(text_color)
        painter.drawText(rect.adjusted(6, 2, -6, -2), int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft), f"Max: {max_val:.2f}")
        painter.drawText(rect.adjusted(6, 2, -6, -2), int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft), f"Min: {min_val:.2f}")
        painter.drawText(rect.adjusted(6, 2, -6, -2), int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight), f"Шаг: {self.step_code} | Δ: {delta_value:+.2f} ({delta_pct:+.2f}%)")
        painter.drawText(rect.adjusted(6, 2, -6, -2), int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight), f"{bucketed[-1].get('time', '—')} | Последнее: {end_value:.2f} | Точек: {len(bucketed)}")
'''
    text = replace_once(text, old_paint_event, new_paint_event, "balance_chart_paint")

    # ------------------------------------------------------------
    # 7) Записать в новый файл
    # ------------------------------------------------------------
    TARGET.write_text(text, encoding="utf-8")

    print("Готово.")
    print(f"Исходник: {SOURCE.resolve()}")
    print(f"Новый файл: {TARGET.resolve()}")
    print("Новая версия: v024_1")


if __name__ == "__main__":
    main()