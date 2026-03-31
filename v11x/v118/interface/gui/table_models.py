# Auto-extracted from app/legacy_runtime.py during one-iteration runtime split
from app.runtime_support import *
from domain.trading.legacy_turtle_engine import TurtleEngine

class PositionTableModel(QAbstractTableModel):
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
        "Sync",
    ]

    def __init__(self):
        super().__init__()
        self.rows: List[dict] = []

    def update_rows(self, rows: List[dict]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return str(section + 1)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        side_text = "🟢 LONG" if row.get("side") == "long" else "🔴 SHORT"
        values = [
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
            row.get("sync_status", "SYNC_OK"),
        ]
        if role == Qt.ItemDataRole.DisplayRole:
            return values[index.column()]
        pnl_pct = float(row.get("pnl_pct", 0.0))
        if role == Qt.ItemDataRole.BackgroundRole:
            sync = str(row.get("sync_status", "SYNC_OK") or "")
            if sync == "STOP_MISSING":
                return QColor(255, 243, 205)
            if sync == "SYNC_DRIFT":
                return QColor(255, 235, 235)
            if sync == "CLOSE_PENDING":
                return QColor(255, 248, 220)
            if sync == "POSITION_GHOST":
                return QColor(245, 235, 255)
            if pnl_pct > 0:
                if pnl_pct >= 10:
                    return QColor(200, 245, 210)
                if pnl_pct >= 5:
                    return QColor(220, 250, 228)
                return QColor(235, 255, 240)
            if pnl_pct < 0:
                if pnl_pct <= -10:
                    return QColor(248, 206, 206)
                if pnl_pct <= -5:
                    return QColor(252, 220, 220)
                return QColor(255, 236, 236)
            return QColor(255, 255, 255)
        if role == Qt.ItemDataRole.ForegroundRole:
            if index.column() in (4, 5, 9, 11, 12):
                return gradient_pnl_color(
                    pnl_pct if index.column() in (4, 5, 12)
                    else -abs(float(row.get('stop_distance_pct' if index.column() == 9 else 'pyramid_distance_pct', 0.0)))
                )
            if index.column() == 1:
                return QColor(0, 120, 35) if row.get("side") == "long" else QColor(180, 30, 30)
            if index.column() == 16:
                sync = str(row.get("sync_status", "SYNC_OK") or "")
                if sync == "SYNC_OK":
                    return QColor(0, 120, 35)
                if sync == "CLOSE_PENDING":
                    return QColor(180, 120, 20)
                if sync == "POSITION_GHOST":
                    return QColor(120, 0, 140)
                return QColor(180, 30, 30)
            return QColor(20, 20, 20)
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() >= 2:
            return int(Qt.AlignmentFlag.AlignCenter)
        return None

class ClosedTradesTableModel(QAbstractTableModel):
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

    def __init__(self):
        super().__init__()
        self.rows: List[dict] = []

    def update_rows(self, rows: List[dict]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return str(section + 1)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        side_text = "🟢 LONG" if row.get("side") == "long" else "🔴 SHORT"
        values = [
            row.get("time"),
            row.get("inst_id"),
            side_text,
            f"{row.get('qty', 0):.6f}",
            f"{row.get('entry_px', 0):.6f}",
            f"{row.get('exit_px', 0):.6f}",
            f"{row.get('pnl', 0):.4f}",
            f"{row.get('pnl_pct', 0):.2f}%",
            format_duration(row.get("duration_sec", 0)),
            str(int(row.get("units", 1))),
            row.get("system_name"),
            row.get("reason"),
        ]
        if role == Qt.ItemDataRole.DisplayRole:
            return values[index.column()]
        pnl_pct = float(row.get("pnl_pct", 0.0))
        if role == Qt.ItemDataRole.BackgroundRole:
            sync = str(row.get("sync_status", "SYNC_OK") or "")
            if sync == "STOP_MISSING":
                return QColor(255, 243, 205)
            if sync == "SYNC_DRIFT":
                return QColor(255, 235, 235)
            if sync == "CLOSE_PENDING":
                return QColor(255, 248, 220)
            if sync == "POSITION_GHOST":
                return QColor(245, 235, 255)
            if pnl_pct > 0:
                return QColor(232, 252, 236)
            if pnl_pct < 0:
                return QColor(255, 235, 235)
        if role == Qt.ItemDataRole.ForegroundRole:
            if index.column() in (6, 7):
                return gradient_pnl_color(pnl_pct)
            if index.column() == 2:
                return QColor(0, 120, 35) if row.get("side") == "long" else QColor(180, 30, 30)
            return QColor(20, 20, 20)
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() in (3,4,5,6,7,8,9):
            return int(Qt.AlignmentFlag.AlignCenter)
        return None
