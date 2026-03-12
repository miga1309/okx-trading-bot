# patch_from_v025_to_v025_1.py
from pathlib import Path

SRC = Path("main_v025.py")
DST = Path("main_v025_1.py")


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        fail(f"Не найден блок: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if not SRC.exists():
        fail(f"Не найден исходный файл: {SRC}")

    text = SRC.read_text(encoding="utf-8")

    # ------------------------------------------------------------
    # 1) Версия / changelog
    # ------------------------------------------------------------
    text = replace_once(
        text,
        '# Version: v025',
        '# Version: v025_1',
        "_header_version",
    )
    text = replace_once(
        text,
        '# Based on: main_v024_4.py',
        '# Based on: main_v025.py',
        "_header_based_on",
    )
    text = replace_once(
        text,
        '# - Fixed pyramiding: removed mandatory break-even lock for first add\n'
        '# - Fixed pyramiding: removed excessive profit-after-add filter\n'
        '# - Fixed entry priority: Turtle 55 now has priority over Turtle 20\n'
        '# - Fixed pyramid grid: next add level now advances from previous trigger',
        '# - Removed "Карта позиций" module from analytics panel\n'
        '# - Widened balance summary card ("Баланс / Использовано / Доступно")\n'
        '# - Widened Turtle regime indicator card in analytics panel\n'
        '# - Cleaned payload/render code related to position_map',
        "_header_changelog",
    )
    text = replace_once(
        text,
        'APP_VERSION = "v025"',
        'APP_VERSION = "v025_1"',
        "_app_version",
    )

    # ------------------------------------------------------------
    # 2) Расширяем карточку баланса и даём ей 2 колонки в сетке статистики
    # ------------------------------------------------------------
    old_metrics_block = '''        labels = [
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
        metrics_layout.setContentsMargins(6, 6, 6, 6)
        metrics_layout.setHorizontalSpacing(6)
        metrics_layout.setVerticalSpacing(4)
        for idx, lbl in enumerate(labels):
            lbl.setProperty("card", "true")
            lbl.setMinimumHeight(24)
            lbl.setMaximumHeight(30)
            metrics_layout.addWidget(lbl, idx // 3, idx % 3)'''

    new_metrics_block = '''        labels = [
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
        metrics_layout.setContentsMargins(6, 6, 6, 6)
        metrics_layout.setHorizontalSpacing(6)
        metrics_layout.setVerticalSpacing(4)

        for lbl in labels:
            lbl.setProperty("card", "true")
            lbl.setMinimumHeight(24)
            lbl.setMaximumHeight(30)

        # v025_1:
        # Делаем строку баланса заметно шире, чтобы "Баланс / Использовано / Доступно"
        # не сжимались при длинных числах.
        self.lbl_balance_summary.setMinimumWidth(420)
        self.lbl_balance_summary.setWordWrap(False)

        metrics_layout.addWidget(self.lbl_status, 0, 0)
        metrics_layout.addWidget(self.lbl_account, 0, 1)
        metrics_layout.addWidget(self.lbl_timeframe, 0, 2)

        metrics_layout.addWidget(self.lbl_balance_summary, 1, 0, 1, 2)
        metrics_layout.addWidget(self.lbl_positions, 1, 2)

        metrics_layout.addWidget(self.lbl_runtime, 2, 0)
        metrics_layout.addWidget(self.lbl_cycle_duration, 2, 1)
        metrics_layout.addWidget(self.lbl_balance_trend, 2, 2)

        metrics_layout.addWidget(self.lbl_risk_panel, 3, 0, 1, 2)
        metrics_layout.addWidget(self.lbl_trade_speed, 3, 2)'''
    text = replace_once(text, old_metrics_block, new_metrics_block, "_metrics_layout_block")

    # ------------------------------------------------------------
    # 3) Убираем "Карта позиций" из аналитики и расширяем Turtle-индикатор
    # ------------------------------------------------------------
    old_analytics_block = '''        analytics_box = QGroupBox("Блок аналитики")
        analytics_layout = QGridLayout(analytics_box)
        self.lbl_open_pnl = QLabel("Open PnL: 0")
        self.lbl_avg_open = QLabel("Средний PnL %: 0")
        self.lbl_best = QLabel("Лучший PnL %: 0")
        self.lbl_worst = QLabel("Худший PnL %: 0")
        self.lbl_long_short = QLabel("Long/Short: 0 / 0")
        self.lbl_realized = QLabel("Реализованный PnL: 0")
        self.lbl_closed_stats = QLabel("Закрытых сделок: 0")
        self.lbl_winrate = QLabel("Winrate: 0%")
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
        analytics_layout.setContentsMargins(6, 6, 6, 6)
        analytics_layout.setHorizontalSpacing(6)
        analytics_layout.setVerticalSpacing(4)
        for idx, lbl in enumerate(analytics_labels):
            lbl.setProperty("card", "true")
            lbl.setMinimumHeight(24)
            lbl.setMaximumHeight(30)
            analytics_layout.addWidget(lbl, idx // 2, idx % 2)
        self.lbl_position_map.setProperty("card", "true")
        self.lbl_position_map.setMaximumHeight(52)
        analytics_layout.addWidget(self.lbl_position_map, 5, 0, 1, 2)
        top_panels.addWidget(analytics_box, 1)'''

    new_analytics_block = '''        analytics_box = QGroupBox("Блок аналитики")
        analytics_layout = QGridLayout(analytics_box)
        self.lbl_open_pnl = QLabel("Open PnL: 0")
        self.lbl_avg_open = QLabel("Средний PnL %: 0")
        self.lbl_best = QLabel("Лучший PnL %: 0")
        self.lbl_worst = QLabel("Худший PnL %: 0")
        self.lbl_long_short = QLabel("Long/Short: 0 / 0")
        self.lbl_realized = QLabel("Реализованный PnL: 0")
        self.lbl_closed_stats = QLabel("Закрытых сделок: 0")
        self.lbl_winrate = QLabel("Winrate: 0%")
        self.lbl_turtle_regime = QLabel("Turtle-индикатор: —")

        analytics_layout.setContentsMargins(6, 6, 6, 6)
        analytics_layout.setHorizontalSpacing(6)
        analytics_layout.setVerticalSpacing(4)

        analytics_cards = [
            self.lbl_open_pnl,
            self.lbl_avg_open,
            self.lbl_best,
            self.lbl_worst,
            self.lbl_long_short,
            self.lbl_realized,
            self.lbl_closed_stats,
            self.lbl_winrate,
        ]
        for lbl in analytics_cards:
            lbl.setProperty("card", "true")
            lbl.setMinimumHeight(24)
            lbl.setMaximumHeight(30)

        self.lbl_turtle_regime.setProperty("card", "true")
        self.lbl_turtle_regime.setMinimumHeight(30)
        self.lbl_turtle_regime.setMaximumHeight(38)
        self.lbl_turtle_regime.setMinimumWidth(420)
        self.lbl_turtle_regime.setWordWrap(False)

        analytics_layout.addWidget(self.lbl_open_pnl, 0, 0)
        analytics_layout.addWidget(self.lbl_avg_open, 0, 1)
        analytics_layout.addWidget(self.lbl_best, 1, 0)
        analytics_layout.addWidget(self.lbl_worst, 1, 1)
        analytics_layout.addWidget(self.lbl_long_short, 2, 0)
        analytics_layout.addWidget(self.lbl_realized, 2, 1)
        analytics_layout.addWidget(self.lbl_closed_stats, 3, 0)
        analytics_layout.addWidget(self.lbl_winrate, 3, 1)

        # v025_1:
        # Turtle-индикатор делаем шире во всю строку.
        analytics_layout.addWidget(self.lbl_turtle_regime, 4, 0, 1, 2)

        top_panels.addWidget(analytics_box, 2)'''
    text = replace_once(text, old_analytics_block, new_analytics_block, "_analytics_block")

    # ------------------------------------------------------------
    # 4) Убираем расчёт position_map из snapshot payload
    # ------------------------------------------------------------
    old_position_map_calc = '''        # Карта позиций
        position_map = []
        for pos in visible_open_positions:
            position_map.append({
                "inst_id": pos.get("inst_id"),
                "side": pos.get("side"),
                "pnl_pct": float(pos.get("pnl_pct", 0.0)),
            })

        position_map.sort(key=lambda x: float(x.get("pnl_pct", 0.0)), reverse=True)
        turtle_regime = self._compute_turtle_regime()'''

    new_position_map_calc = '''        turtle_regime = self._compute_turtle_regime()'''
    text = replace_once(text, old_position_map_calc, new_position_map_calc, "_position_map_calc")

    # ------------------------------------------------------------
    # 5) Убираем position_map из analytics payload
    # ------------------------------------------------------------
    text = replace_once(
        text,
        '                "position_map": position_map,\n',
        '',
        "_position_map_payload",
    )

    # ------------------------------------------------------------
    # 6) Убираем отрисовку lbl_position_map в update_snapshot
    # ------------------------------------------------------------
    old_position_map_render = '''        position_map = analytics.get('position_map', [])
        if position_map:
            chunks = []
            for item in position_map:
                side_icon = '🟢' if item.get('side') == 'long' else '🔴'
                chunks.append(f"{side_icon} {item.get('inst_id')}: {float(item.get('pnl_pct', 0.0)):+.2f}%")
            self.lbl_position_map.setText("Карта позиций: " + " | ".join(chunks))
        else:
            self.lbl_position_map.setText("Карта позиций: —")
        self._apply_status_style(self.lbl_open_pnl, analytics.get('open_pnl', 0.0))'''

    new_position_map_render = '''        self._apply_status_style(self.lbl_open_pnl, analytics.get('open_pnl', 0.0))'''
    text = replace_once(text, old_position_map_render, new_position_map_render, "_position_map_render")

    # ------------------------------------------------------------
    # 7) Немного усиливаем общий приоритет ширины верхних блоков
    # ------------------------------------------------------------
    text = replace_once(
        text,
        '        top_panels.addWidget(metrics_box, 3)',
        '        top_panels.addWidget(metrics_box, 4)',
        "_metrics_stretch",
    )

    DST.write_text(text, encoding="utf-8")
    print(f"Готово: {DST}")


if __name__ == "__main__":
    main()