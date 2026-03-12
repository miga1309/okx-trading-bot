# patch_v024_3_to_v024_4_turtle_relax_and_pnl_chart.py
# Создаёт новый файл main_v024_4.py на базе main_v024_3.py
#
# Изменения v024_4:
# - Убран flat-filter на входе (остальные защиты оставлены)
# - required_score снижен до 2
# - Добавлен Turtle-индикатор режима рынка в блок аналитики
# - График переделан в стиле "PnL за сегодня" (вдохновлено OKX Android)
# - Добавлен changelog в заголовок новой версии
#
# Использование:
#   python patch_v024_3_to_v024_4_turtle_relax_and_pnl_chart.py

from pathlib import Path
from datetime import datetime
import sys

SOURCE = Path("main_v024_3.py")
TARGET = Path("main_v024_4.py")


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
    # 1) Версия + changelog
    # ------------------------------------------------------------
    old_header = '''# ============================================================
# OKX Turtle Bot
# Version: v024_3
# Date: 2026-03-11
# Based on: main_v024_2.py
#
# Changelog:
# - Fixed analytics fields used by GUI
# - Implemented working "Карта позиций"
# - Added day/week balance change calculations
# - Added risk/trade speed analytics for dashboard
# ============================================================

'''
    new_header = f'''# ============================================================
# OKX Turtle Bot
# Version: v024_4
# Date: {datetime.now().strftime("%Y-%m-%d")}
# Based on: main_v024_3.py
#
# Changelog:
# - Removed flat-filter from entry logic
# - Reduced breakout required_score to 2
# - Added Turtle market regime indicator to analytics panel
# - Redesigned chart into OKX-like "PnL за сегодня" style
# ============================================================

'''
    text = replace_once(text, old_header, new_header, "changelog_header")
    text = replace_once(text, 'APP_VERSION = "v024_3"', 'APP_VERSION = "v024_4"', "app_version")

    # ------------------------------------------------------------
    # 2) Убираем flat-filter на входе
    # ------------------------------------------------------------
    old_flat_block = '''        is_flat, flat_reason = self.is_flat_market(candles, price, atr)
        if is_flat:
            logging.info("%s: пропуск входа, flat-filter (%s)", inst_id, flat_reason)
            return

'''
    new_flat_block = '''        # v024_4: flat-filter отключён для большего соответствия классической Turtle-логике.
        # Оставляем structure-filter, liquidity-filter и breakout confirmation.
'''
    text = replace_once(text, old_flat_block, new_flat_block, "remove_flat_filter")

    # ------------------------------------------------------------
    # 3) required_score -> 2
    # ------------------------------------------------------------
    old_score_block = '''        tf_sec = self._timeframe_seconds()
        if tf_sec <= 900:
            required_score = 4
        else:
            required_score = 4
'''
    new_score_block = '''        tf_sec = self._timeframe_seconds()
        required_score = 2
'''
    text = replace_once(text, old_score_block, new_score_block, "required_score")

    # ------------------------------------------------------------
    # 4) Добавляем Turtle-индикатор режима рынка
    # ------------------------------------------------------------
    old_confirm_tail = '''        return False, ", ".join(reasons[:3]) if reasons else f"недостаточно подтверждений ({score})"
'''
    new_confirm_tail = '''        return False, ", ".join(reasons[:3]) if reasons else f"недостаточно подтверждений ({score})"

    def _compute_turtle_regime(self) -> dict:
        probe_inst = "BTC-USDT-SWAP" if "BTC-USDT-SWAP" in self.gateway.swap_ids else (self.gateway.swap_ids[0] if self.gateway.swap_ids else "")
        if not probe_inst:
            return {
                "label": "Нет данных",
                "score": 0,
                "channel_atr_ratio": 0.0,
                "efficiency_ratio": 0.0,
                "atr_pct": 0.0,
            }

        try:
            candles = self.gateway.get_candles(
                probe_inst,
                self.cfg.timeframe,
                max(self.cfg.atr_period, self.cfg.long_entry_period, 32) + 8
            )
        except Exception:
            candles = []

        if len(candles) < max(self.cfg.atr_period + 2, 20):
            return {
                "label": "Нет данных",
                "score": 0,
                "channel_atr_ratio": 0.0,
                "efficiency_ratio": 0.0,
                "atr_pct": 0.0,
            }

        atr = self.calculate_atr_from_candles(candles, self.cfg.atr_period)
        price = float(candles[-1][4] or 0.0)
        if atr <= 0 or price <= 0:
            return {
                "label": "Нет данных",
                "score": 0,
                "channel_atr_ratio": 0.0,
                "efficiency_ratio": 0.0,
                "atr_pct": 0.0,
            }

        window = candles[-min(len(candles), max(20, self.cfg.flat_lookback_candles)):]
        highs = [float(c[2]) for c in window]
        lows = [float(c[3]) for c in window]
        closes = [float(c[4]) for c in window]

        channel = max(highs) - min(lows)
        channel_atr_ratio = channel / max(atr, 1e-12)
        atr_pct = (atr / price) * 100.0

        net_move = abs(closes[-1] - closes[0]) if len(closes) > 1 else 0.0
        travel = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
        efficiency_ratio = (net_move / travel) if travel > 0 else 0.0

        center = (max(highs) + min(lows)) / 2.0
        breakout_pressure = abs(closes[-1] - center) / max(channel, 1e-12)

        score = 0
        if channel_atr_ratio >= 3.0:
            score += 1
        if efficiency_ratio >= 0.28:
            score += 1
        if atr_pct >= max(0.10, self.cfg.min_atr_pct * 0.75):
            score += 1
        if breakout_pressure >= 0.33:
            score += 1

        if score >= 3:
            label = "Трендовый"
        elif score == 2:
            label = "Нейтральный"
        else:
            label = "Флэт"

        return {
            "label": label,
            "score": score,
            "channel_atr_ratio": round(channel_atr_ratio, 2),
            "efficiency_ratio": round(efficiency_ratio, 2),
            "atr_pct": round(atr_pct, 3),
            "instrument": probe_inst,
        }
'''
    text = replace_once(text, old_confirm_tail, new_confirm_tail, "add_turtle_regime_method")

    # ------------------------------------------------------------
    # 5) В analytics payload добавляем regime
    # ------------------------------------------------------------
    old_position_map_block = '''        # Карта позиций
        position_map = []
        for pos in visible_open_positions:
            position_map.append({
                "inst_id": pos.get("inst_id"),
                "side": pos.get("side"),
                "pnl_pct": float(pos.get("pnl_pct", 0.0)),
            })

        position_map.sort(key=lambda x: float(x.get("pnl_pct", 0.0)), reverse=True)
        balance_total = float(data[0].get("totalEq") or 0.0) if data else 0.0
'''
    new_position_map_block = '''        # Карта позиций
        position_map = []
        for pos in visible_open_positions:
            position_map.append({
                "inst_id": pos.get("inst_id"),
                "side": pos.get("side"),
                "pnl_pct": float(pos.get("pnl_pct", 0.0)),
            })

        position_map.sort(key=lambda x: float(x.get("pnl_pct", 0.0)), reverse=True)
        turtle_regime = self._compute_turtle_regime()

        balance_total = float(data[0].get("totalEq") or 0.0) if data else 0.0
'''
    text = replace_once(text, old_position_map_block, new_position_map_block, "regime_before_balance")

    old_payload_analytics = '''            "analytics": {
                "open_pnl": open_pnl,
                "avg_open_pnl_pct": avg_pnl_pct,
                "best_open_pnl_pct": best_open,
                "worst_open_pnl_pct": worst_open,
                "long_count": longs,
                "short_count": shorts,
                "closed_count": len(visible_closed_trades),
                "realized_pnl": realized_pnl,
                "wins": wins,
                "losses": losses,
                "winrate": winrate,
                "day_change_pct": day_change_pct,
                "week_change_pct": week_change_pct,
                "used_risk_pct": used_risk_pct,
                "max_risk_budget_pct": max_risk_budget_pct,
                "trades_today": trades_today,
                "avg_duration_sec": avg_duration_sec,
                "position_map": position_map,
            },
'''
    new_payload_analytics = '''            "analytics": {
                "open_pnl": open_pnl,
                "avg_open_pnl_pct": avg_pnl_pct,
                "best_open_pnl_pct": best_open,
                "worst_open_pnl_pct": worst_open,
                "long_count": longs,
                "short_count": shorts,
                "closed_count": len(visible_closed_trades),
                "realized_pnl": realized_pnl,
                "wins": wins,
                "losses": losses,
                "winrate": winrate,
                "day_change_pct": day_change_pct,
                "week_change_pct": week_change_pct,
                "used_risk_pct": used_risk_pct,
                "max_risk_budget_pct": max_risk_budget_pct,
                "trades_today": trades_today,
                "avg_duration_sec": avg_duration_sec,
                "position_map": position_map,
                "turtle_regime_label": turtle_regime.get("label", "—"),
                "turtle_regime_score": turtle_regime.get("score", 0),
                "turtle_regime_channel_atr": turtle_regime.get("channel_atr_ratio", 0.0),
                "turtle_regime_efficiency": turtle_regime.get("efficiency_ratio", 0.0),
                "turtle_regime_atr_pct": turtle_regime.get("atr_pct", 0.0),
                "turtle_regime_instrument": turtle_regime.get("instrument", "—"),
            },
'''
    text = replace_once(text, old_payload_analytics, new_payload_analytics, "analytics_payload")

    # ------------------------------------------------------------
    # 6) Добавляем label в блок аналитики
    # ------------------------------------------------------------
    old_analytics_ui = '''        self.lbl_winrate = QLabel("Winrate: 0%")
        self.lbl_position_map = QLabel("Карта позиций: —")
        self.lbl_position_map.setWordWrap(True)
        analytics_labels = [
            self.lbl_open_pnl,
            self.lbl_avg_open,
            self.lbl_best,
            self.lbl_worst,
            self.lbl_long_short,
            self.lbl_realized,
            self.lbl_closed_stats,
            self.lbl_winrate,
        ]
'''
    new_analytics_ui = '''        self.lbl_winrate = QLabel("Winrate: 0%")
        self.lbl_turtle_regime = QLabel("Turtle-индикатор: —")
        self.lbl_position_map = QLabel("Карта позиций: —")
        self.lbl_position_map.setWordWrap(True)
        analytics_labels = [
            self.lbl_open_pnl,
            self.lbl_avg_open,
            self.lbl_best,
            self.lbl_worst,
            self.lbl_long_short,
            self.lbl_realized,
            self.lbl_closed_stats,
            self.lbl_winrate,
            self.lbl_turtle_regime,
        ]
'''
    text = replace_once(text, old_analytics_ui, new_analytics_ui, "analytics_ui_label")

    old_analytics_layout = '''        for idx, lbl in enumerate(analytics_labels):
            lbl.setProperty("card", "true")
            lbl.setMinimumHeight(24)
            lbl.setMaximumHeight(30)
            analytics_layout.addWidget(lbl, idx // 2, idx % 2)
        self.lbl_position_map.setProperty("card", "true")
        self.lbl_position_map.setMaximumHeight(52)
        analytics_layout.addWidget(self.lbl_position_map, 4, 0, 1, 2)
'''
    new_analytics_layout = '''        for idx, lbl in enumerate(analytics_labels):
            lbl.setProperty("card", "true")
            lbl.setMinimumHeight(24)
            lbl.setMaximumHeight(30)
            analytics_layout.addWidget(lbl, idx // 2, idx % 2)
        self.lbl_position_map.setProperty("card", "true")
        self.lbl_position_map.setMaximumHeight(52)
        analytics_layout.addWidget(self.lbl_position_map, 5, 0, 1, 2)
'''
    text = replace_once(text, old_analytics_layout, new_analytics_layout, "analytics_layout")

    # ------------------------------------------------------------
    # 7) Обновляем on_snapshot для индикатора
    # ------------------------------------------------------------
    old_on_snapshot_piece = '''        self.lbl_trade_speed.setText(f"Сделок сегодня: {analytics.get('trades_today', 0)} | Средняя длительность: {format_duration(analytics.get('avg_duration_sec', 0))}")
        position_map = analytics.get('position_map', [])
'''
    new_on_snapshot_piece = '''        self.lbl_trade_speed.setText(f"Сделок сегодня: {analytics.get('trades_today', 0)} | Средняя длительность: {format_duration(analytics.get('avg_duration_sec', 0))}")

        regime_label = analytics.get('turtle_regime_label', '—')
        regime_score = analytics.get('turtle_regime_score', 0)
        regime_inst = analytics.get('turtle_regime_instrument', '—')
        regime_channel = analytics.get('turtle_regime_channel_atr', 0.0)
        regime_eff = analytics.get('turtle_regime_efficiency', 0.0)
        regime_atr_pct = analytics.get('turtle_regime_atr_pct', 0.0)
        self.lbl_turtle_regime.setText(
            f"Turtle-индикатор: {regime_label} | score {regime_score}/4 | "
            f"{regime_inst} | ch/ATR {regime_channel:.2f} | eff {regime_eff:.2f} | ATR {regime_atr_pct:.2f}%"
        )
        if regime_label == "Трендовый":
            self.lbl_turtle_regime.setStyleSheet("color: #16a34a; font-weight: 700;")
        elif regime_label == "Нейтральный":
            self.lbl_turtle_regime.setStyleSheet("color: #d97706; font-weight: 700;")
        elif regime_label == "Флэт":
            self.lbl_turtle_regime.setStyleSheet("color: #dc2626; font-weight: 700;")
        else:
            self.lbl_turtle_regime.setStyleSheet("")

        position_map = analytics.get('position_map', [])
'''
    text = replace_once(text, old_on_snapshot_piece, new_on_snapshot_piece, "on_snapshot_regime")

    # ------------------------------------------------------------
    # 8) Меняем заголовок графика
    # ------------------------------------------------------------
    text = replace_once(
        text,
        '        self.lbl_balance_chart_title = QLabel("График баланса")',
        '        self.lbl_balance_chart_title = QLabel("PnL за сегодня")',
        "chart_title"
    )

    # ------------------------------------------------------------
    # 9) Переделываем paintEvent графика в стиль PnL за сегодня
    # ------------------------------------------------------------
    old_paint = '''    def paintEvent(self, event) -> None:
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
    new_paint = '''    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = self.rect()
        rect = outer.adjusted(8, 8, -8, -8)

        bg_color = QColor(12, 14, 18) if self.dark_theme else QColor(255, 255, 255)
        border_color = QColor(32, 37, 45) if self.dark_theme else QColor(225, 228, 235)
        muted_color = QColor(124, 132, 145) if self.dark_theme else QColor(128, 128, 128)
        text_color = QColor(245, 247, 250) if self.dark_theme else QColor(28, 28, 28)
        pos_color = QColor(35, 199, 104)
        neg_color = QColor(239, 68, 68)
        grid_color = QColor(38, 45, 56) if self.dark_theme else QColor(234, 236, 240)

        painter.fillRect(outer, bg_color)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(rect, 14, 14)

        bucketed = self._bucket_points()
        if not bucketed:
            painter.setPen(muted_color)
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "PnL за сегодня появится после накопления истории")
            return

        raw_values = [float(point.get("value", 0.0)) for point in bucketed]
        base_value = raw_values[0]
        pnl_values = [v - base_value for v in raw_values]
        current_pnl = pnl_values[-1]
        current_pct = (current_pnl / base_value * 100.0) if abs(base_value) > 1e-12 else 0.0

        # OKX-like header
        header_rect = rect.adjusted(16, 12, -16, -rect.height() + 56)
        pnl_color = pos_color if current_pnl >= 0 else neg_color
        painter.setPen(pnl_color)
        header_font = painter.font()
        header_font.setPointSize(15)
        header_font.setBold(True)
        painter.setFont(header_font)
        painter.drawText(header_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), f"{current_pnl:+.2f} USDT")

        sub_rect = rect.adjusted(16, 36, -16, -rect.height() + 72)
        sub_font = painter.font()
        sub_font.setPointSize(10)
        sub_font.setBold(False)
        painter.setFont(sub_font)
        painter.drawText(sub_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), f"{current_pct:+.2f}%  ·  {bucketed[-1].get('time', '—')}")

        plot = rect.adjusted(18, 78, -18, -24)

        min_val = min(min(pnl_values), 0.0)
        max_val = max(max(pnl_values), 0.0)
        span = max_val - min_val
        pad = max(span * 0.18, 0.5)
        min_plot = min_val - pad
        max_plot = max_val + pad
        if abs(max_plot - min_plot) < 1e-12:
            max_plot += 1.0
            min_plot -= 1.0

        def value_to_y(value: float) -> int:
            return int(plot.bottom() - ((value - min_plot) / (max_plot - min_plot)) * plot.height())

        zero_y = value_to_y(0.0)

        # Сетка и Y labels справа
        painter.setPen(QPen(grid_color, 1, Qt.PenStyle.DashLine))
        y_marks = []
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = int(plot.top() + plot.height() * frac)
            value = max_plot - (max_plot - min_plot) * frac
            y_marks.append((y, value))
            painter.drawLine(plot.left(), y, plot.right(), y)

        painter.setPen(muted_color)
        for y, value in y_marks:
            painter.drawText(plot.right() - 56, y - 2, f"{value:+.2f}")

        # Нулевая линия
        painter.setPen(QPen(QColor(110, 118, 132), 1, Qt.PenStyle.DashLine))
        painter.drawLine(plot.left(), zero_y, plot.right(), zero_y)

        if len(pnl_values) == 1:
            x_positions = [plot.center().x()]
        else:
            step_x = plot.width() / (len(pnl_values) - 1)
            x_positions = [plot.left() + i * step_x for i in range(len(pnl_values))]

        line_points = [(int(x), value_to_y(val)) for x, val in zip(x_positions, pnl_values)]
        line_color = pos_color if current_pnl >= 0 else neg_color
        area_color = QColor(line_color.red(), line_color.green(), line_color.blue(), 70)

        # Заполнение до нулевой линии
        area = QPolygon()
        area.append(QPoint(line_points[0][0], zero_y))
        for x, y in line_points:
            area.append(QPoint(x, y))
        area.append(QPoint(line_points[-1][0], zero_y))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(area_color)
        painter.drawPolygon(area)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(line_color, 2))
        for i in range(1, len(line_points)):
            painter.drawLine(line_points[i - 1][0], line_points[i - 1][1], line_points[i][0], line_points[i][1])

        # Последняя точка
        last_x, last_y = line_points[-1]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(line_color)
        painter.drawEllipse(last_x - 4, last_y - 4, 8, 8)

        # Маркеры закрытых сделок
        marker_index = {str(point.get("time")): i for i, point in enumerate(bucketed)}
        for marker in self.markers[-200:]:
            idx = marker_index.get(str(marker.get("bucket_time")))
            if idx is None or idx >= len(line_points):
                continue
            x, y = line_points[idx]
            pnl = float(marker.get("pnl", 0.0))
            color = pos_color if pnl >= 0 else neg_color
            painter.setBrush(color)
            painter.drawEllipse(x - 2, y - 9, 4, 4)

        # Нижние подписи X
        painter.setPen(muted_color)
        show_indices = sorted(set([0, len(bucketed) // 2, len(bucketed) - 1]))
        for idx in show_indices:
            if idx < 0 or idx >= len(bucketed):
                continue
            x = line_points[idx][0]
            label = str(bucketed[idx].get("time", "—"))
            painter.drawText(x - 22, plot.bottom() + 16, label)
'''
    text = replace_once(text, old_paint, new_paint, "pnl_chart_style")

    TARGET.write_text(text, encoding="utf-8")

    print("Готово.")
    print(f"Исходник:  {SOURCE.resolve()}")
    print(f"Новый файл: {TARGET.resolve()}")
    print("Новая версия: v024_4")
    print()
    print("Что проверить:")
    print("1) Входов должно стать больше: flat-filter снят, required_score=2")
    print("2) В аналитике должен появиться Turtle-индикатор")
    print("3) График должен выглядеть как PnL-карта: крупный PnL, %, нулевая линия, area-fill")
    print("4) Старый файл main_v024_3.py не изменяется")


if __name__ == "__main__":
    main()