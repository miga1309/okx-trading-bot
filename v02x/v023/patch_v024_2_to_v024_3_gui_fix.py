# patch_v024_2_to_v024_3_gui_fix.py
# Создаёт новый файл main_v024_3.py на базе main_v024_2.py
#
# Что исправляет:
# - Делает рабочей "Карту позиций"
# - Заполняет day_change_pct / week_change_pct
# - Заполняет used_risk_pct / max_risk_budget_pct
# - Заполняет trades_today / avg_duration_sec
# - Обновляет changelog и версию
#
# Использование:
#   python patch_v024_2_to_v024_3_gui_fix.py

from pathlib import Path
from datetime import datetime
import sys

SOURCE = Path("main_v024_2.py")
TARGET = Path("main_v024_3.py")


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
        'APP_VERSION = "v024_2"',
        'APP_VERSION = "v024_3"',
        "app_version",
    )

    # ------------------------------------------------------------
    # 2) Changelog header
    # ------------------------------------------------------------
    old_header = '''# ============================================================
# OKX Turtle Bot
# Version: v024_2
# Date: 2026-03-11
# Based on: main_v024_1.py
#
# Changelog:
# - Removed extra statistics fields from GUI
# - Kept "Юнитов" naming in tables
# - Improved balance chart with Y-axis labels and scale
# - Created as a new versioned file
# ============================================================

'''
    new_header = f'''# ============================================================
# OKX Turtle Bot
# Version: v024_3
# Date: {datetime.now().strftime("%Y-%m-%d")}
# Based on: main_v024_2.py
#
# Changelog:
# - Fixed analytics fields used by GUI
# - Implemented working "Карта позиций"
# - Added day/week balance change calculations
# - Added risk/trade speed analytics for dashboard
# ============================================================

'''
    text = replace_once(text, old_header, new_header, "changelog_header")

    # ------------------------------------------------------------
    # 3) Исправить analytics в emit_snapshot()
    # ------------------------------------------------------------
    old_analytics_block = '''        visible_open_positions = [x for x in open_positions if not is_hidden_instrument(x.get("inst_id"))]
        visible_closed_trades = [x for x in self.closed_trades if not is_hidden_instrument(x.inst_id)]

        open_pnl = sum(float(x.get("unrealized_pnl", 0.0)) for x in visible_open_positions)
        longs = sum(1 for x in visible_open_positions if x.get("side") == "long")
        shorts = sum(1 for x in visible_open_positions if x.get("side") == "short")
        avg_pnl_pct = sum(float(x.get("pnl_pct", 0.0)) for x in visible_open_positions) / len(visible_open_positions) if visible_open_positions else 0.0
        best_open = max((float(x.get("pnl_pct", 0.0)) for x in visible_open_positions), default=0.0)
        worst_open = min((float(x.get("pnl_pct", 0.0)) for x in visible_open_positions), default=0.0)
        realized_pnl = sum(x.pnl for x in visible_closed_trades)
        wins = sum(1 for x in visible_closed_trades if x.pnl > 0)
        losses = sum(1 for x in visible_closed_trades if x.pnl < 0)
        winrate = wins / len(visible_closed_trades) * 100.0 if visible_closed_trades else 0.0

        now_full = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
'''
    new_analytics_block = '''        visible_open_positions = [x for x in open_positions if not is_hidden_instrument(x.get("inst_id"))]
        visible_closed_trades = [x for x in self.closed_trades if not is_hidden_instrument(x.inst_id)]

        open_pnl = sum(float(x.get("unrealized_pnl", 0.0)) for x in visible_open_positions)
        longs = sum(1 for x in visible_open_positions if x.get("side") == "long")
        shorts = sum(1 for x in visible_open_positions if x.get("side") == "short")
        avg_pnl_pct = sum(float(x.get("pnl_pct", 0.0)) for x in visible_open_positions) / len(visible_open_positions) if visible_open_positions else 0.0
        best_open = max((float(x.get("pnl_pct", 0.0)) for x in visible_open_positions), default=0.0)
        worst_open = min((float(x.get("pnl_pct", 0.0)) for x in visible_open_positions), default=0.0)
        realized_pnl = sum(x.pnl for x in visible_closed_trades)
        wins = sum(1 for x in visible_closed_trades if x.pnl > 0)
        losses = sum(1 for x in visible_closed_trades if x.pnl < 0)
        winrate = wins / len(visible_closed_trades) * 100.0 if visible_closed_trades else 0.0

        now_full = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Изменение баланса за день и за 7 дней
        day_change_pct = 0.0
        week_change_pct = 0.0

        history_with_dt = []
        for item in self.balance_history:
            try:
                dt = datetime.strptime(str(item.get("time", "")), "%Y-%m-%d %H:%M:%S")
                val = float(item.get("balance_total", 0.0))
                history_with_dt.append((dt, val))
            except Exception:
                continue

        if history_with_dt:
            history_with_dt.sort(key=lambda x: x[0])
            current_balance_for_change = history_with_dt[-1][1]

            day_cutoff = datetime.now() - timedelta(days=1)
            week_cutoff = datetime.now() - timedelta(days=7)

            day_candidates = [v for dt, v in history_with_dt if dt <= day_cutoff]
            week_candidates = [v for dt, v in history_with_dt if dt <= week_cutoff]

            if day_candidates and abs(day_candidates[-1]) > 1e-12:
                day_change_pct = ((current_balance_for_change - day_candidates[-1]) / day_candidates[-1]) * 100.0

            if week_candidates and abs(week_candidates[-1]) > 1e-12:
                week_change_pct = ((current_balance_for_change - week_candidates[-1]) / week_candidates[-1]) * 100.0

        # Использовано риска
        used_risk_pct = sum(
            max(0.0, float(pos.get("stop_distance_pct", 0.0)))
            for pos in visible_open_positions
        )
        max_risk_budget_pct = max(
            0.0,
            len(visible_open_positions) * float(self.cfg.risk_per_trade_pct or 0.0)
        )

        # Сделки сегодня / средняя длительность
        today_str = datetime.now().strftime("%Y-%m-%d")
        trades_today = 0
        durations_today = []
        for trade in visible_closed_trades:
            try:
                if str(trade.time).startswith(today_str):
                    trades_today += 1
                    durations_today.append(int(trade.duration_sec or 0))
            except Exception:
                continue
        avg_duration_sec = int(sum(durations_today) / len(durations_today)) if durations_today else 0

        # Карта позиций
        position_map = []
        for pos in visible_open_positions:
            position_map.append({
                "inst_id": pos.get("inst_id"),
                "side": pos.get("side"),
                "pnl_pct": float(pos.get("pnl_pct", 0.0)),
            })

        position_map.sort(key=lambda x: float(x.get("pnl_pct", 0.0)), reverse=True)
'''
    text = replace_once(text, old_analytics_block, new_analytics_block, "analytics_prep_block")

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
            },
'''
    text = replace_once(text, old_payload_analytics, new_payload_analytics, "payload_analytics")

    TARGET.write_text(text, encoding="utf-8")

    print("Готово.")
    print(f"Исходник:  {SOURCE.resolve()}")
    print(f"Новый файл: {TARGET.resolve()}")
    print("Новая версия: v024_3")
    print()
    print("Что исправлено в GUI:")
    print("- 'Карта позиций' теперь заполняется")
    print("- 'Изменение баланса' теперь рассчитывается")
    print("- 'Использовано риска' теперь заполняется")
    print("- 'Сделок сегодня / Средняя длительность' теперь заполняется")


if __name__ == "__main__":
    main()